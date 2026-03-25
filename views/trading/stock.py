from typing import Any

import pandas as pd
import streamlit as st

from config.auth import is_paid, is_pro, require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences, show_legal_disclaimer
from data.database import get_autopilot_jobs, get_autopilot_logs, log_user_activity
from trading.autopilot_engine import is_running, start_background_autopilot, stop_background_autopilot
from trading.kis_api import KISApi, is_market_open, market_status_text
from trading.kiwoom_api import KiwoomApi
from views.trading._stock_manual_order import render_manual_order as render_stock_manual_order


def _init_defaults(username: str) -> None:
    st.session_state.setdefault("broker_api", None)
    st.session_state.setdefault("broker_name", "")
    st.session_state.setdefault("trade_log", [])

    saved = load_user_preferences(username, "autopilot")
    defaults: dict[str, Any] = {
        "ap_market": "KOSPI",
        "ap_mode": "일반 추천",
        "ap_capital": 1_000_000,
        "ap_max_stocks": 5,
        "ap_max_per": 20,
        "ap_stop_loss": 5.0,
        "ap_take_profit": 15.0,
        "ap_daily_limit": 5.0,
        "ap_usdkrw": 1350.0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, saved.get(key, value))

    saved_trade = load_user_preferences(username, "trading_stock")
    st.session_state.setdefault("stock_broker_code", str(saved_trade.get("last_selected_broker", "KIS") or "KIS"))
    st.session_state.setdefault("stock_trading_mode", str(saved_trade.get("trading_mode", "모의투자") or "모의투자"))
    st.session_state.setdefault("stock_last_ticker", str(saved_trade.get("last_used_ticker", "005930") or "005930"))
    st.session_state.setdefault("stock_buy_ticker", st.session_state["stock_last_ticker"])
    st.session_state.setdefault("stock_sell_ticker", st.session_state["stock_last_ticker"])
    st.session_state.setdefault(
        "_stock_pref_last",
        (
            st.session_state["stock_broker_code"],
            st.session_state["stock_trading_mode"],
            st.session_state["stock_last_ticker"],
        ),
    )


def _save_stock_preferences(username: str, log_change: bool = False) -> None:
    settings = {
        "last_selected_broker": str(st.session_state.get("stock_broker_code") or "KIS"),
        "trading_mode": str(st.session_state.get("stock_trading_mode") or "모의투자"),
        "last_used_ticker": str(st.session_state.get("stock_last_ticker") or ""),
    }
    current = (
        settings["last_selected_broker"],
        settings["trading_mode"],
        settings["last_used_ticker"],
    )
    previous = st.session_state.get("_stock_pref_last")
    if previous == current:
        return
    save_user_preferences(username, "trading_stock", settings)
    if log_change:
        log_user_activity(username, "settings_changed", "국내주식 매매 설정 변경", "매매(국내주식)")
    st.session_state["_stock_pref_last"] = current


def _render_broker_connect(username: str) -> None:
    st.subheader("증권사 API 연결")
    st.session_state.setdefault("broker_app_key", "")
    st.session_state.setdefault("broker_secret", "")
    st.session_state.setdefault("broker_account", "")

    brokers = {"한국투자증권 (KIS)": "KIS", "키움증권": "KIWOOM"}
    labels = list(brokers.keys())
    selected_code = str(st.session_state.get("stock_broker_code") or "KIS")
    default_label = next((label for label, code in brokers.items() if code == selected_code), labels[0])
    st.session_state.setdefault("stock_broker_label", default_label)
    broker_label = str(st.selectbox("증권사 선택", labels, key="stock_broker_label") or labels[0])
    broker_code = brokers[broker_label]
    st.session_state["stock_broker_code"] = broker_code
    modes = ["모의투자", "실전투자"]

    col1, col2 = st.columns(2)
    with col1:
        app_key = st.text_input("App Key", type="password", key="broker_app_key")
        account_no = st.text_input("계좌번호", key="broker_account")
    with col2:
        app_secret = st.text_input("Secret Key" if broker_code == "KIWOOM" else "App Secret", type="password", key="broker_secret")
        mode = str(st.selectbox("거래 모드", modes, key="stock_trading_mode") or "모의투자")

    _save_stock_preferences(username, log_change=True)

    if mode == "모의투자":
        base_url = "https://openapivts.koreainvestment.com:29443" if broker_code == "KIS" else "https://mockapi.kiwoom.com"
    else:
        base_url = "https://openapi.koreainvestment.com:9443" if broker_code == "KIS" else "https://api.kiwoom.com"

    target = (broker_code, mode, base_url)
    connected_target = st.session_state.get("_stock_connected_target")
    if st.session_state.get("broker_api") is not None and connected_target and connected_target != target:
        st.session_state["broker_api"] = None
        st.session_state["broker_name"] = ""
        st.session_state["_stock_connected_target"] = None
        st.warning("증권사/거래 모드가 변경되어 기존 연결을 해제했습니다. 안전을 위해 다시 API 연결을 진행해 주세요.")

    if st.button("API 연결", type="primary", use_container_width=True):
        if not (app_key and app_secret and account_no):
            st.error("모든 필드를 입력하세요.")
            return
        try:
            api = KISApi(app_key, app_secret, account_no, base_url) if broker_code == "KIS" else KiwoomApi(app_key, app_secret, account_no, base_url)
            api.get_access_token()
            st.session_state["broker_api"] = api
            st.session_state["broker_name"] = broker_label
            st.session_state["_stock_connected_target"] = target
            save_user_preferences(
                username,
                "broker_api",
                {
                    "broker": broker_code,
                    "account_tail": account_no[-4:] if len(account_no) >= 4 else account_no,
                    "trading_mode": mode,
                },
            )
            st.success(f"{broker_label} API 연결 성공 ({mode})")
        except Exception as e:
            st.error(f"연결 실패: {e}")


def _render_autopilot(username: str) -> None:
    st.subheader("오토파일럿")
    c1, c2 = st.columns(2)
    with c1:
        market = str(st.selectbox("시장", ["KOSPI", "KOSDAQ", "US"], key="ap_market") or "KOSPI")
        mode = str(st.selectbox("추천 모드", ["일반 추천", "🔥 공격적 추천"], key="ap_mode") or "일반 추천")
        capital = int(st.number_input("투자금 (원)", min_value=100_000, step=100_000, key="ap_capital", format="%d"))
        max_stocks = int(st.slider("최대 보유 종목", 1, 10, key="ap_max_stocks"))
    with c2:
        max_per = int(st.slider("종목당 비중 (%)", 10, 50, key="ap_max_per"))
        sl = float(st.slider("손절 (%)", 1.0, 20.0, key="ap_stop_loss"))
        tp = float(st.slider("익절 (%)", 5.0, 50.0, key="ap_take_profit"))
        daily = float(st.slider("일일 손실 한도 (%)", 1.0, 20.0, key="ap_daily_limit"))
        usdkrw = float(st.number_input("USD/KRW 환율 (US용)", min_value=900.0, max_value=2000.0, key="ap_usdkrw"))

    save_user_preferences(
        username,
        "autopilot",
        {
            "ap_market": market,
            "ap_mode": mode,
            "ap_capital": capital,
            "ap_max_stocks": max_stocks,
            "ap_max_per": max_per,
            "ap_stop_loss": sl,
            "ap_take_profit": tp,
            "ap_daily_limit": daily,
            "ap_usdkrw": usdkrw,
        },
    )

    notice = st.session_state.pop("_ap_notice", None)
    if isinstance(notice, dict):
        level = str(notice.get("level") or "info")
        message = str(notice.get("message") or "")
        if message:
            if level == "success":
                st.success(message)
            elif level == "warning":
                st.warning(message)
            elif level == "error":
                st.error(message)
            else:
                st.info(message)

    jobs = get_autopilot_jobs(username)
    job = next((j for j in jobs if int(str(j.get("slot_idx", -1))) == 0), None)
    thread_running = is_running(username, 0)
    db_running = bool(job and str(job.get("status", "")) == "running")
    if db_running and not thread_running:
        st.warning("오토파일럿 상태가 남아 있지만 백그라운드 스레드는 실행 중이 아닙니다. 상태 초기화를 권장합니다.")
        if st.button("상태 초기화(중지)", key="ap_reset_stale", use_container_width=True):
            try:
                stop_background_autopilot(username, 0)
                st.session_state["_ap_notice"] = {
                    "level": "info",
                    "message": "오토파일럿 상태를 초기화했습니다.",
                }
            except Exception as e:
                st.session_state["_ap_notice"] = {
                    "level": "error",
                    "message": f"상태 초기화 실패: {e}",
                }
            st.rerun()
    running = thread_running

    if market == "US":
        st.info("US 오토파일럿은 현재 거래 이력 기록(시뮬레이션) 기반으로 동작합니다. 실제 브로커 주문 연동은 KR 시장 중심으로 제공됩니다.")

    left, right = st.columns(2)
    with left:
        if not running and st.button("🚀 AP-1 시작", use_container_width=True, type="primary"):
            try:
                if market in {"KOSPI", "KOSDAQ"} and not is_market_open():
                    st.session_state["_ap_notice"] = {
                        "level": "warning",
                        "message": f"⚠️ 현재 장 운영시간이 아닙니다. ({market_status_text()})",
                    }
                    st.rerun()
                started = start_background_autopilot(
                    username=username,
                    slot_idx=0,
                    market=market,
                    mode=mode,
                    capital=capital,
                    max_stocks=max_stocks,
                    max_per=max_per,
                    stop_loss=sl,
                    take_profit=tp,
                    daily_limit=daily,
                    usdkrw=usdkrw,
                )
                if started:
                    log_user_activity(username, "autopilot_started", f"{market}/{mode}", "매매(국내/미국주식)")
                    st.session_state["_ap_notice"] = {
                        "level": "success",
                        "message": "🚀 AP-1 시작 요청 완료. 수 초 내 상태/로그가 갱신됩니다.",
                    }
                else:
                    st.session_state["_ap_notice"] = {
                        "level": "warning",
                        "message": "⚠️ AP-1이 이미 실행 중입니다.",
                    }
            except Exception as e:
                st.session_state["_ap_notice"] = {
                    "level": "error",
                    "message": f"오토파일럿 시작 실패: {e}",
                }
            st.rerun()
    with right:
        if running and st.button("🛑 AP-1 중지", use_container_width=True, type="primary"):
            try:
                stop_background_autopilot(username, 0)
                log_user_activity(username, "autopilot_stopped", "AP-1", "매매(국내/미국주식)")
                st.session_state["_ap_notice"] = {
                    "level": "success",
                    "message": "🛑 AP-1 중지 요청 완료.",
                }
            except Exception as e:
                st.session_state["_ap_notice"] = {
                    "level": "error",
                    "message": f"오토파일럿 중지 실패: {e}",
                }
            st.rerun()

    if job:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("상태", str(job.get("status", "-")))
        m2.metric("실행 횟수", int(str(job.get("run_count", 0))))
        m3.metric("일간 손익", f"{float(str(job.get('daily_pnl', 0.0))):+.2f}%")
        m4.metric("다음 실행", str(job.get("next_run_at") or "-"))

    logs = get_autopilot_logs(username, 0, limit=30)
    if isinstance(logs, pd.DataFrame) and not logs.empty and "message" in logs.columns:
        st.text_area("최근 로그", "\n".join(logs["message"].astype(str).tail(15).tolist()), height=180)
    elif isinstance(logs, list) and logs:
        st.text_area("최근 로그", "\n".join([str(x) for x in logs[-15:]]), height=180)
    elif running:
        st.info("오토파일럿 실행 중입니다. 최초 스캔/로그 반영까지 수 초가 걸릴 수 있습니다.")


def render_stock(user: dict[str, object]) -> None:
    _ = (require_auth, inject_pro_css, is_paid, is_pro)
    username = str(user["username"])
    visit_key = f"_visit_logged_stock_{username}"
    if not st.session_state.get(visit_key):
        log_user_activity(username, "page_visit", "", "매매(국내주식)")
        st.session_state[visit_key] = True

    _init_defaults(username)

    st.title("🤖 자동매매 봇")
    st.warning("이 기능은 실제 주문을 실행할 수 있습니다. 반드시 모의투자로 충분히 검증한 뒤 사용하세요.")

    tab_order, tab_auto = st.tabs(["⚡ 주문", "🚀 오토파일럿"])
    with tab_order:
        _render_broker_connect(username)
        st.markdown("---")
        render_stock_manual_order(lambda log_change: _save_stock_preferences(username, log_change=log_change))
    with tab_auto:
        _render_autopilot(username)

    show_legal_disclaimer()
