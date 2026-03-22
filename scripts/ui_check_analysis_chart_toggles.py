"""UI-level check: analysis chart auto-toggle persistence.

Validates real UI + DB consistency for:
- data_auto_rerun (입력 변경 시 자동 조회)
- ta_auto_rerun (입력 변경 시 자동 재분석)

Run:
  python scripts/ui_check_analysis_chart_toggles.py
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


def _resolve_toggle_checkbox(root_locator, label_text: str):
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


def _ensure_toggle_on(sidebar, toggle_label: str) -> None:
    label, checkbox = _resolve_toggle_checkbox(sidebar, toggle_label)
    if not checkbox.is_checked():
        label.click(force=True, timeout=10_000)
        expect(checkbox).to_be_checked(timeout=15_000)
    time.sleep(0.75)
    _, checkbox_after = _resolve_toggle_checkbox(sidebar, toggle_label)
    if not checkbox_after.is_checked():
        raise AssertionError(f"Toggle did not remain checked after rerender: {toggle_label}")


def _assert_pref_true(load_user_preferences, username: str, key: str) -> None:
    pref = load_user_preferences(username, "analysis")
    if pref.get(key) is not True:
        raise AssertionError(f"{key} was not persisted to DB as True")


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from auth.core import create_user, delete_user, verify_user  # noqa: PLC0415
    from config.styles import load_user_preferences  # noqa: PLC0415
    from data import database  # noqa: PLC0415
    from data.database import DB_PATH, create_session_token  # noqa: PLC0415

    database.init_db()

    username = f"ui_chart_{int(time.time())}"
    password = f"P@ss-{int(time.time())}"

    created = create_user(username, password, role="user", plan="free")
    if not created:
        raise RuntimeError(f"Failed to create user: {username}")
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

        _wait_for_http(base_url)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(f"{base_url}/?_auth={token}")

            sidebar = page.locator('[data-testid="stSidebar"]')
            expect(sidebar).to_be_visible(timeout=30_000)

            # Open analysis page
            _click_sidebar_nav(sidebar, "분석")
            expect(page.locator("h1").filter(has_text="분석")).to_be_visible(timeout=30_000)

            # Data analysis subsection toggle
            _click_radio_option(page, "데이터분석")
            _ensure_toggle_on(sidebar, "입력 변경 시 자동 조회")

            # Technical analysis subsection toggle
            _click_radio_option(page, "기술적분석")
            _ensure_toggle_on(sidebar, "입력 변경 시 자동 재분석")

            # Navigate away and back, then assert both still on
            _click_sidebar_nav(sidebar, "홈")
            _click_sidebar_nav(sidebar, "분석")
            expect(page.locator("h1").filter(has_text="분석")).to_be_visible(timeout=30_000)

            _click_radio_option(page, "데이터분석")
            _, data_checkbox = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 조회")
            if not data_checkbox.is_checked():
                raise AssertionError("data_auto_rerun toggle did not persist after navigation")

            _click_radio_option(page, "기술적분석")
            _, ta_checkbox = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 재분석")
            if not ta_checkbox.is_checked():
                raise AssertionError("ta_auto_rerun toggle did not persist after navigation")

            _assert_pref_true(load_user_preferences, username, "data_auto_rerun")
            _assert_pref_true(load_user_preferences, username, "ta_auto_rerun")

            ctx.close()
            browser.close()

        print("[PASS] data_auto_rerun and ta_auto_rerun persisted across UI navigation.")
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
