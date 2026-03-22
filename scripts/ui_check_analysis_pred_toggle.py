"""UI-level check: analysis AI prediction auto-toggle persistence.

This script is intentionally NOT part of pytest/CI.

What it validates (real browser + real Streamlit runtime):
1) Create a temporary Plus user + session token
2) Open the app authenticated via `/?_auth=<token>`
3) Navigate to 분석 → AI판단 → AI예측
4) Turn ON '입력 변경 시 자동 예측' (pred_auto_rerun)
5) Navigate away and return
6) Confirm the toggle is still ON

Run:
  python scripts/ui_check_analysis_pred_toggle.py

Exit code:
  0 on success, 1 on failure
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
        except Exception as e:  # noqa: BLE001 - surfacing last error
            last_err = e
            time.sleep(0.25)
    raise RuntimeError(f"Server did not become ready: {url} ({last_err})")


def _resolve_toggle_checkbox(root_locator, label_text: str):
    """Return locator to underlying checkbox input for a Streamlit toggle/checkbox."""

    label = root_locator.locator("label").filter(has_text=label_text).first
    expect(label).to_be_visible(timeout=30_000)

    for_id = label.get_attribute("for")
    if for_id:
        checkbox = root_locator.locator(f"#{for_id}")
    else:
        checkbox = root_locator.get_by_role("checkbox", name=label_text).first
        if checkbox.count() == 0:
            checkbox = label.locator('input[type="checkbox"]').first
    expect(checkbox).to_have_count(1)
    return label, checkbox


def _click_sidebar_nav(sidebar, page_title: str) -> None:
    """Click a Streamlit navigation item by its title text."""

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
        page.locator('label').filter(has_text=text).first,
        page.get_by_text(text).first,
    ]
    last_err: Optional[Exception] = None
    for loc in locators:
        try:
            expect(loc).to_be_visible(timeout=20_000)
            loc.click(timeout=20_000)
            return
        except Exception as e:  # noqa: BLE001 - try next strategy
            last_err = e
    raise RuntimeError(f"Failed to click radio option: {text} ({last_err})")


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    # Import after sys.path update
    from auth.core import create_user, delete_user, verify_user  # noqa: PLC0415
    from config.styles import load_user_preferences  # noqa: PLC0415
    from data import database  # noqa: PLC0415
    from data.database import DB_PATH, create_session_token  # noqa: PLC0415

    database.init_db()

    username = f"ui_pref_{int(time.time())}"
    password = f"P@ss-{int(time.time())}"

    created = create_user(username, password, role="user", plan="plus")
    if not created:
        raise RuntimeError(f"Failed to create user (already exists?): {username}")
    user = verify_user(username, password)
    if user is None:
        raise RuntimeError("Failed to verify freshly created user")

    user_id_raw = user.get("id")
    if isinstance(user_id_raw, int):
        user_id = user_id_raw
    elif isinstance(user_id_raw, str) and user_id_raw.isdigit():
        user_id = int(user_id_raw)
    else:
        raise RuntimeError(f"Unexpected user id type: {type(user_id_raw).__name__}")
    token = create_session_token(
        username=str(user["username"]),
        user_id=user_id,
        role=str(user["role"]),
        plan=str(user["plan"]),
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

        _wait_for_http(f"{base_url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()

            page.goto(f"{base_url}/?_auth={token}")

            sidebar = page.locator('[data-testid="stSidebar"]')
            expect(sidebar).to_be_visible(timeout=30_000)

            # Navigate to 분석
            _click_sidebar_nav(sidebar, "분석")

            # Wait for analysis page to render
            expect(page.locator('h1').filter(has_text="분석")).to_be_visible(timeout=30_000)

            # Select AI판단 → AI예측
            _click_radio_option(page, "AI판단")
            _click_radio_option(page, "AI예측")

            # Wait until prediction section is rendered
            expect(page.get_by_text("AI 예측").first).to_be_visible(timeout=30_000)

            # Toggle ON
            label, checkbox = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 예측")
            if not checkbox.is_checked():
                label.click(force=True, timeout=10_000)
                expect(checkbox).to_be_checked(timeout=15_000)

            # Streamlit reruns on widget change; re-resolve after rerender
            time.sleep(0.75)
            _, checkbox_after = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 예측")
            if not checkbox_after.is_checked():
                raise AssertionError("Toggle did not remain checked after rerender")

            pref_after = load_user_preferences(username, "analysis")
            if pref_after.get("pred_auto_rerun") is not True:
                raise AssertionError("pred_auto_rerun was not persisted to DB after toggle")

            # Navigate away and back
            _click_sidebar_nav(sidebar, "홈")

            _click_sidebar_nav(sidebar, "분석")

            expect(page.locator('h1').filter(has_text="분석")).to_be_visible(timeout=30_000)

            _click_radio_option(page, "AI판단")
            _click_radio_option(page, "AI예측")

            expect(page.get_by_text("AI 예측").first).to_be_visible(timeout=30_000)

            _, checkbox2 = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 예측")
            if not checkbox2.is_checked():
                raise AssertionError("pred_auto_rerun toggle was not persisted (expected checked)")

            pref_after_nav = load_user_preferences(username, "analysis")
            if pref_after_nav.get("pred_auto_rerun") is not True:
                raise AssertionError("pred_auto_rerun DB value drifted after navigation")

            ctx.close()
            browser.close()

        print("[PASS] pred_auto_rerun persisted across UI rerender and navigation.")
        return 0
    finally:
        # Cleanup: stop server, remove created user + related rows
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
    except Exception as e:  # noqa: BLE001 - top-level tool
        safe_msg = str(e).encode("unicode_escape", errors="backslashreplace").decode("ascii", errors="ignore")
        print(f"[FAIL] {type(e).__name__}: {safe_msg}")
        raise SystemExit(1)
