"""Full analysis subsection UI smoke check.

This script exercises all major analysis subfeatures in a real Streamlit session:
- 차트분석: 데이터분석 / 글로벌마켓 / 기술적분석
- AI판단: 종목스크리너 / 종목추천 / AI예측
- 투자도구: 백테스팅 / 리스크분석 / 뉴스감성분석

Run:
  python scripts/ui_check_analysis_full_subsections.py
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


def _wait_for_http(url: str, timeout_s: float = 40.0) -> None:
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


def _click_tab(page, text: str) -> None:
    tab = page.get_by_role("tab", name=text).first
    expect(tab).to_be_visible(timeout=20_000)
    tab.click(timeout=20_000)


def _click_sidebar_button(sidebar, name: str) -> None:
    button = sidebar.get_by_role("button", name=name).first
    expect(button).to_be_visible(timeout=20_000)
    button.click(timeout=20_000)


def _assert_no_fatal_error(page) -> None:
    content = page.content()
    fatal_markers = [
        "Traceback",
        "StreamlitAPIException",
        "ModuleNotFoundError",
        "TypeError:",
        "분석 모듈 로드 실패",
        "데이터를 가져올 수 없습니다.",
        "Failed to fetch data.",
        "Prediction failed:",
    ]
    for marker in fatal_markers:
        if marker in content:
            raise AssertionError(f"Fatal runtime marker detected: {marker}")


def _wait_spinner_clear(page) -> None:
    spinner = page.locator('[data-testid="stSpinner"]')
    expect(spinner).to_have_count(0, timeout=60_000)


def _assert_clean(page, page_errors: list[str], console_errors: list[str]) -> None:
    _assert_no_fatal_error(page)
    if page_errors:
        raise AssertionError(f"Page errors detected: {page_errors[:3]}")
    if console_errors:
        raise AssertionError(f"Console errors detected: {console_errors[:3]}")


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from auth.core import create_user, delete_user, verify_user  # noqa: PLC0415
    from data import database  # noqa: PLC0415
    from data.database import DB_PATH, create_session_token  # noqa: PLC0415

    database.init_db()

    username = f"ui_full_{int(time.time())}"
    password = f"P@ss-{int(time.time())}"

    created = create_user(username, password, role="user", plan="pro")
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
            ctx = browser.new_context(viewport={"width": 1600, "height": 1200})
            page = ctx.new_page()
            page_errors: list[str] = []
            console_errors: list[str] = []

            def _on_page_error(exc) -> None:
                page_errors.append(str(exc))

            def _on_console(msg) -> None:
                if str(msg.type).lower() == "error":
                    console_errors.append(msg.text)

            page.on("pageerror", _on_page_error)
            page.on("console", _on_console)
            page.goto(f"{base_url}/?_auth={token}")

            sidebar = page.locator('[data-testid="stSidebar"]')
            expect(sidebar).to_be_visible(timeout=30_000)

            _click_sidebar_nav(sidebar, "분석")
            expect(page.locator("h1").filter(has_text="분석")).to_be_visible(timeout=30_000)

            # 1) 차트분석
            _click_radio_option(page, "차트분석")
            _click_radio_option(page, "데이터분석")
            expect(page.get_by_text("주가 데이터 분석").first).to_be_visible(timeout=20_000)
            _click_sidebar_button(sidebar, "조회")
            _wait_spinner_clear(page)
            expect(page.locator('[data-testid="stPlotlyChart"]').first).to_be_visible(timeout=30_000)
            _assert_clean(page, page_errors, console_errors)

            _click_radio_option(page, "글로벌마켓")
            expect(page.get_by_text("글로벌 마켓").first).to_be_visible(timeout=20_000)
            _click_tab(page, "암호화폐")
            page.get_by_role("button", name="암호화폐 데이터 로드").first.click(timeout=20_000)
            page.get_by_role("button", name="차트 로드").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _click_tab(page, "경제지표")
            page.get_by_role("button", name="경제지표 로드").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _click_tab(page, "글로벌 지수")
            page.get_by_role("button", name="글로벌 지수 로드").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _click_tab(page, "투자자 동향")
            page.get_by_role("button", name="투자자 동향 로드").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _assert_clean(page, page_errors, console_errors)

            _click_radio_option(page, "기술적분석")
            expect(page.get_by_text("기술적 분석").first).to_be_visible(timeout=20_000)
            _click_sidebar_button(sidebar, "분석 실행")
            _wait_spinner_clear(page)
            expect(page.get_by_text("종합 시그널").first).to_be_visible(timeout=30_000)
            _assert_clean(page, page_errors, console_errors)

            # 2) AI판단
            _click_radio_option(page, "AI판단")
            _click_radio_option(page, "종목스크리너")
            expect(page.get_by_text("종목 스크리너").first).to_be_visible(timeout=20_000)
            _click_sidebar_button(sidebar, "Run Screener")
            _wait_spinner_clear(page)
            _assert_clean(page, page_errors, console_errors)

            _click_radio_option(page, "종목추천")
            expect(page.get_by_text("AI 종목추천").first).to_be_visible(timeout=20_000)
            page.get_by_role("button", name="종목 추천 시작").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _assert_clean(page, page_errors, console_errors)

            _click_radio_option(page, "AI예측")
            expect(page.get_by_text("AI 예측").first).to_be_visible(timeout=20_000)
            _click_sidebar_button(sidebar, "Run Prediction")
            _wait_spinner_clear(page)
            expect(page.get_by_text("Models Used").first).to_be_visible(timeout=30_000)
            _assert_clean(page, page_errors, console_errors)

            # 3) 투자도구
            _click_radio_option(page, "투자도구")
            _click_tab(page, "백테스팅")
            _click_sidebar_button(sidebar, "백테스팅 실행")
            _wait_spinner_clear(page)
            expect(page.get_by_text("백테스팅 결과").first).to_be_visible(timeout=30_000)
            if page.get_by_role("button", name="최적화 시작").count() > 0:
                page.get_by_role("button", name="최적화 시작").first.click(timeout=20_000)
                _wait_spinner_clear(page)
            page.get_by_role("button", name="모든 전략 비교 실행").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            expect(page.get_by_text("전략별 자산 추이 비교").first).to_be_visible(timeout=30_000)
            _assert_clean(page, page_errors, console_errors)

            _click_tab(page, "리스크분석")
            _click_tab(page, "Risk Metrics")
            _click_sidebar_button(sidebar, "Analyze Risk")
            _wait_spinner_clear(page)
            _click_tab(page, "Monte Carlo Simulation")
            page.get_by_role("button", name="Run Monte Carlo").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _click_tab(page, "Efficient Frontier")
            page.get_by_role("button", name="Calculate Efficient Frontier").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _click_tab(page, "Leverage Simulator")
            page.get_by_role("button", name="Run Leverage Simulation").first.click(timeout=20_000)
            _wait_spinner_clear(page)
            _assert_clean(page, page_errors, console_errors)

            _click_tab(page, "뉴스감성분석")
            _click_sidebar_button(sidebar, "Fetch News")
            _wait_spinner_clear(page)
            expect(page.get_by_text("Total Articles").first).to_be_visible(timeout=30_000)
            _assert_clean(page, page_errors, console_errors)

            ctx.close()
            browser.close()

        print("[PASS] Full analysis subsection smoke run completed without fatal runtime errors.")
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
