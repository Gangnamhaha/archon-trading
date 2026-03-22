"""UI-level check: analysis user-switch isolation.

Verifies that analysis toggle/session state from user A does not leak to user B.

Run:
  python scripts/ui_check_analysis_user_switch_isolation.py
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


def _set_pred_toggle_on(page, sidebar) -> None:
    _click_sidebar_nav(sidebar, "분석")
    expect(page.locator("h1").filter(has_text="분석")).to_be_visible(timeout=30_000)
    _click_radio_option(page, "AI판단")
    _click_radio_option(page, "AI예측")
    label, checkbox = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 예측")
    if not checkbox.is_checked():
        label.click(force=True, timeout=10_000)
        expect(checkbox).to_be_checked(timeout=15_000)


def _assert_pred_toggle_off_for_fresh_user(page, sidebar) -> None:
    _click_sidebar_nav(sidebar, "분석")
    expect(page.locator("h1").filter(has_text="분석")).to_be_visible(timeout=30_000)
    _click_radio_option(page, "AI판단")
    _click_radio_option(page, "AI예측")
    _, checkbox = _resolve_toggle_checkbox(sidebar, "입력 변경 시 자동 예측")
    if checkbox.is_checked():
        raise AssertionError("pred_auto_rerun leaked from previous user session")


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from auth.core import create_user, delete_user, verify_user  # noqa: PLC0415
    from data import database  # noqa: PLC0415
    from data.database import DB_PATH, create_session_token  # noqa: PLC0415

    database.init_db()

    suffix = int(time.time())
    username_a = f"ui_iso_a_{suffix}"
    username_b = f"ui_iso_b_{suffix}"
    password = f"P@ss-{suffix}"

    for username in (username_a, username_b):
        if not create_user(username, password, role="user", plan="plus"):
            raise RuntimeError(f"Failed to create user: {username}")

    user_a = verify_user(username_a, password)
    user_b = verify_user(username_b, password)
    if user_a is None or user_b is None:
        raise RuntimeError("Failed to verify created users")

    def _uid(u: dict[str, object]) -> int:
        raw = u.get("id")
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
        raise RuntimeError("Unexpected user id type")

    token_a = create_session_token(
        username=username_a,
        user_id=_uid(user_a),
        role=str(user_a.get("role", "user")),
        plan=str(user_a.get("plan", "plus")),
        session_timeout=86400,
        max_sessions=2,
    )
    token_b = create_session_token(
        username=username_b,
        user_id=_uid(user_b),
        role=str(user_b.get("role", "user")),
        plan=str(user_b.get("plan", "plus")),
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

            # User A: enable pred toggle
            ctx_a = browser.new_context(viewport={"width": 1400, "height": 1000})
            page_a = ctx_a.new_page()
            page_a.goto(f"{base_url}/?_auth={token_a}")
            sidebar_a = page_a.locator('[data-testid="stSidebar"]')
            expect(sidebar_a).to_be_visible(timeout=30_000)
            _set_pred_toggle_on(page_a, sidebar_a)
            ctx_a.close()

            # User B: must not inherit A's toggle state
            ctx_b = browser.new_context(viewport={"width": 1400, "height": 1000})
            page_b = ctx_b.new_page()
            page_b.goto(f"{base_url}/?_auth={token_b}")
            sidebar_b = page_b.locator('[data-testid="stSidebar"]')
            expect(sidebar_b).to_be_visible(timeout=30_000)
            _assert_pred_toggle_off_for_fresh_user(page_b, sidebar_b)
            ctx_b.close()

            browser.close()

        print("[PASS] Analysis session state is isolated across user switch (no toggle leakage).")
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
            delete_user(_uid(user_a) if user_a else -1)
        with contextlib.suppress(Exception):
            delete_user(_uid(user_b) if user_b else -1)

        with contextlib.suppress(Exception):
            import sqlite3

            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM user_settings WHERE username IN (?, ?)", (username_a, username_b))
            conn.execute("DELETE FROM session_tokens WHERE username IN (?, ?)", (username_a, username_b))
            conn.commit()
            conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:  # noqa: BLE001
        safe_msg = str(e).encode("unicode_escape", errors="backslashreplace").decode("ascii", errors="ignore")
        print(f"[FAIL] {type(e).__name__}: {safe_msg}")
        raise SystemExit(1)
