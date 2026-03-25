"""Full-app UI smoke test (non-destructive).

This script launches Streamlit locally, logs in via session token, then navigates:
- 홈
- 분석 (full analysis subsections smoke)
- 매매 (stocks autopilot config view + FX/Crypto smoke)
- 포트폴리오 (basic render)
- 설정 (switch sections)
- 관리자 page reachable (should show admin login form when not admin)

It intentionally avoids placing real broker orders.

Run:
  python scripts/ui_check_full_app_smoke.py
"""

from __future__ import annotations

import contextlib
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _get_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_for_http(url: str, timeout_s: float = 30.0) -> None:
    import urllib.request

    start = time.time()
    last_err: Optional[Exception] = None
    while time.time() - start < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= int(resp.status) < 500:
                    return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.25)
    raise RuntimeError(f"Server did not become ready: {url} ({last_err})")


def _click_sidebar_nav(sidebar, page_title: str) -> None:
    for role in ("link", "button"):
        try:
            sidebar.get_by_role(role, name=page_title).click(timeout=10_000)
            return
        except PlaywrightError:
            pass
    sidebar.get_by_text(page_title, exact=True).click(timeout=10_000)


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from auth.core import create_user, delete_user, verify_user  # noqa: PLC0415
    from data import database  # noqa: PLC0415
    from data.database import DB_PATH, create_session_token  # noqa: PLC0415

    database.init_db()

    username = f"ui_fullapp_{int(time.time())}"
    password = f"P@ss-{int(time.time())}"

    if not create_user(username, password, role="user", plan="pro"):
        raise RuntimeError("Failed to create user")
    user = verify_user(username, password)
    if user is None:
        raise RuntimeError("Failed to verify user")

    raw_id = user.get("id")
    if isinstance(raw_id, int):
        user_id = raw_id
    elif isinstance(raw_id, str) and raw_id.isdigit():
        user_id = int(raw_id)
    else:
        raise RuntimeError("Unexpected user id")

    token = create_session_token(
        username=username,
        user_id=user_id,
        role=str(user.get("role", "user")),
        plan=str(user.get("plan", "pro")),
        session_timeout=86400,
        max_sessions=2,
    )

    port = _get_free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc: Optional[subprocess.Popen[str]] = None

    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.port",
                str(port),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_for_http(base_url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1600, "height": 1200})
            page = ctx.new_page()
            page.goto(f"{base_url}/?_auth={token}")
            sidebar = page.locator('[data-testid="stSidebar"]')
            expect(sidebar).to_be_visible(timeout=30_000)

            # Home
            _click_sidebar_nav(sidebar, "홈")
            expect(page.get_by_text("Market Overview").first).to_be_visible(timeout=30_000)

            # Analysis: reuse existing comprehensive script by importing and running it separately
            # (keeps this script focused on cross-page navigation)
            import subprocess as _sp

            rc = _sp.run([sys.executable, "scripts/ui_check_analysis_full_subsections.py"], cwd=str(root)).returncode
            if rc != 0:
                raise AssertionError("Analysis full subsection smoke failed")

            # Trading stocks autopilot config visible
            _click_sidebar_nav(sidebar, "매매")
            expect(page.get_by_text("⚡ 매매").first).to_be_visible(timeout=30_000)
            expect(page.get_by_text("자동매매 봇").first).to_be_visible(timeout=30_000)
            page.get_by_role("tab", name="🚀 오토파일럿").first.click(timeout=20_000)
            expect(page.get_by_text("오토파일럿").first).to_be_attached(timeout=30_000)

            # Trading FX/Crypto smoke
            rc2 = _sp.run([sys.executable, "scripts/ui_check_trading_fx_crypto_smoke.py"], cwd=str(root)).returncode
            if rc2 != 0:
                raise AssertionError("Trading FX/Crypto smoke failed")

            # Portfolio page render
            _click_sidebar_nav(sidebar, "포트폴리오")
            expect(page.get_by_text("포트폴리오 트래커").first).to_be_visible(timeout=30_000)

            # Settings page render
            _click_sidebar_nav(sidebar, "설정")
            expect(page.get_by_text("⚙️ 설정").first).to_be_visible(timeout=30_000)
            # Switch a section to ensure no crash
            page.get_by_text("고객지원").first.click(timeout=20_000)
            expect(page.get_by_text("자주하는질문").first).to_be_visible(timeout=30_000)

            # Admin page reachable (should show admin login form)
            _click_sidebar_nav(sidebar, "관리자")
            expect(page.get_by_text("관리자").first).to_be_visible(timeout=30_000)

            ctx.close()
            browser.close()

        print("[PASS] Full app smoke completed.")
        return 0
    finally:
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=10)
            if proc.stdout is not None:
                with contextlib.suppress(Exception):
                    proc.stdout.close()

        with contextlib.suppress(Exception):
            delete_user(user_id)

        with contextlib.suppress(Exception):
            import sqlite3

            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM user_settings WHERE username=?", (username,))
            conn.execute("DELETE FROM session_tokens WHERE username=?", (username,))
            conn.commit()
            conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        safe_msg = str(e).encode("unicode_escape", errors="backslashreplace").decode("ascii", errors="ignore")
        print(f"[FAIL] {type(e).__name__}: {safe_msg}")
        raise SystemExit(1)
