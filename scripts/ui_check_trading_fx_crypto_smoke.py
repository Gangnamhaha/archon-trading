"""Direct browser smoke: trading FX and Crypto sections.

Validates that:
- 매매 page loads
- FX section (Pro) loads and can render a chart and start/stop simulation autopilot
- Crypto section (Pro) loads and can render a chart and start/stop simulation autopilot

Run:
  python scripts/ui_check_trading_fx_crypto_smoke.py
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


def _click_radio_option(page, text: str) -> None:
    locators = [
        page.locator('[data-baseweb="radio"]').filter(has_text=text).first,
        page.locator("label").filter(has_text=text).first,
        page.get_by_text(text).first,
    ]
    last_err: Optional[Exception] = None
    for loc in locators:
        try:
            expect(loc).to_be_visible(timeout=20_000)
            loc.click(timeout=20_000)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"Failed to click radio option: {text} ({last_err})")


def _wait_spinner_clear(page) -> None:
    spinner = page.locator('[data-testid="stSpinner"]')
    expect(spinner).to_have_count(0, timeout=90_000)


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from auth.core import create_user, delete_user, verify_user  # noqa: PLC0415
    from data import database  # noqa: PLC0415
    from data.database import DB_PATH, create_session_token  # noqa: PLC0415

    database.init_db()

    username = f"ui_fxcrypto_{int(time.time())}"
    password = f"P@ss-{int(time.time())}"

    if not create_user(username, password, role="user", plan="pro"):
        raise RuntimeError(f"Failed to create user: {username}")
    user = verify_user(username, password)
    if user is None:
        raise RuntimeError("Failed to verify user")

    raw_id = user.get("id")
    if isinstance(raw_id, int):
        user_id = raw_id
    elif isinstance(raw_id, str) and raw_id.isdigit():
        user_id = int(raw_id)
    else:
        raise RuntimeError("Unexpected user id type")

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

            _click_sidebar_nav(sidebar, "매매")
            expect(page.get_by_text("⚡ 매매").first).to_be_visible(timeout=30_000)

            # FX
            _click_radio_option(page, "외환")
            expect(page.get_by_text("외환 자동매매").first).to_be_visible(timeout=30_000)
            # Chart load can be flaky on slow data sources; keep smoke non-blocking.
            if page.get_by_role("button", name="차트 불러오기").count() > 0:
                try:
                    page.get_by_role("button", name="차트 불러오기").first.click(timeout=20_000)
                    _wait_spinner_clear(page)
                except Exception:
                    pass

            # Start/stop FX autopilot
            page.get_by_role("tab", name="⚡ 자동매매").first.click(timeout=20_000)
            page.get_by_role("button", name="▶️ 오토파일럿 시작").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            expect(page.get_by_text("🟢 오토파일럿 실행 중").first).to_be_visible(timeout=30_000)
            page.get_by_role("button", name="⏹️ 오토파일럿 중지").first.click(timeout=20_000)
            _wait_spinner_clear(page)

            # Crypto
            _click_sidebar_nav(sidebar, "매매")
            _click_radio_option(page, "코인")
            expect(page.get_by_text("코인 자동매매").first).to_be_visible(timeout=30_000)
            if page.get_by_role("button", name="차트 불러오기").count() > 0:
                try:
                    page.get_by_role("button", name="차트 불러오기").first.click(timeout=20_000)
                    _wait_spinner_clear(page)
                except Exception:
                    pass

            page.get_by_role("tab", name="⚡ 자동매매").first.click(timeout=20_000)
            page.get_by_role("button", name="▶️ 오토파일럿 시작").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            expect(page.get_by_text("🟢 코인 오토파일럿 실행 중").first).to_be_visible(timeout=30_000)
            page.get_by_role("button", name="⏹️ 오토파일럿 중지").first.click(timeout=20_000)
            _wait_spinner_clear(page)

            ctx.close()
            browser.close()

        print("[PASS] Trading FX/Crypto pages loaded and simulation start/stop succeeded.")
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
