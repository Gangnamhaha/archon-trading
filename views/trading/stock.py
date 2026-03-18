from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from config.auth import is_paid, is_pro, require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences, show_legal_disclaimer
from data.database import add_trade, get_autopilot_jobs, get_autopilot_logs
from trading.autopilot_engine import is_running, start_background_autopilot, stop_background_autopilot
from trading.kis_api import KISApi, market_status_text
from trading.kiwoom_api import KiwoomApi


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


def _render_broker_connect(username: str) -> None:
    st.subheader("증권사 API 연결")
    saved = load_user_preferences(username, "broker_api")
    if saved:
        st.session_state.setdefault("broker_app_key", saved.get("app_key", ""))
        st.session_state.setdefault("broker_secret", saved.get("app_secret", ""))
        st.session_state.setdefault("broker_account", saved.get("account_no", ""))

    brokers = {"한국투자증권 (KIS)": "KIS", "키움증권": "KIWOOM"}
    labels = list(brokers.keys())
    broker_label = str(st.selectbox("증권사 선택", labels) or labels[0])
    broker_code = brokers[broker_label]
    modes = ["모의투자", "실전투자"]

    col1, col2 = st.columns(2)
    with col1:
        app_key = st.text_input("App Key", type="password", key="broker_app_key")
        account_no = st.text_input("계좌번호", key="broker_account")
    with col2:
        app_secret = st.text_input("Secret Key" if broker_code == "KIWOOM" else "App Secret", type="password", key="broker_secret")
        mode = st.selectbox("거래 모드", modes)

    if mode == "모의투자":
        base_url = "https://openapivts.koreainvestment.com:29443" if broker_code == "KIS" else "https://mockapi.kiwoom.com"
    else:
        base_url = "https://openapi.koreainvestment.com:9443" if broker_code == "KIS" else "https://api.kiwoom.com"

    if st.button("API 연결", type="primary", use_container_width=True):
        if not (app_key and app_secret and account_no):
            st.error("모든 필드를 입력하세요.")
            return
        try:
            api = KISApi(app_key, app_secret, account_no, base_url) if broker_code == "KIS" else KiwoomApi(app_key, app_secret, account_no, base_url)
            api.get_access_token()
            st.session_state["broker_api"] = api
            st.session_state["broker_name"] = broker_label
            save_user_preferences(
                username,
                "broker_api",
                {
                    "broker": broker_code,
                    "app_key": app_key,
                    "app_secret": app_secret,
                    "account_no": account_no,
                    "trading_mode": mode,
                },
            )
            st.success(f"{broker_label} API 연결 성공 ({mode})")
        except Exception as e:
            st.error(f"연결 실패: {e}")


def _render_manual_order() -> None:
    api = st.session_state.get("broker_api")
    if api is None:
        st.info("수동 주문을 사용하려면 증권사 API를 연결하세요.")
        return

    status = api.get_status()
    c1, c2, c3 = st.columns(3)
    c1.metric("연결 상태", "연결됨" if status.get("has_token") else "미연결")
    c2.metric("증권사", str(st.session_state.get("broker_name") or "-"))
    c3.metric("계좌", str(status.get("account") or "-"))
    st.caption(market_status_text())

    if st.button("💰 잔고 조회", use_container_width=True, key="btn_balance"):
        with st.spinner("잔고 조회 중..."):
            bal = api.get_balance()
        if "error" in bal:
            st.error(f"잔고 조회 실패: {bal['error']}")
        else:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("예수금", f"{int(bal.get('예수금', 0)):,}원")
            b2.metric("총매입금액", f"{int(bal.get('총매입금액', 0)):,}원")
            b3.metric("총평가금액", f"{int(bal.get('총평가금액', 0)):,}원")
            pnl = int(bal.get("총평가손익", 0))
            b4.metric("총평가손익", f"{pnl:+,}원", delta=f"{pnl:+,}")

            holdings = bal.get("holdings", [])
            if holdings:
                st.markdown("##### 보유 종목")
                st.dataframe(
                    pd.DataFrame(holdings),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "수익률": st.column_config.NumberColumn(format="%.2f%%"),
                        "평가금액": st.column_config.NumberColumn(format="%d"),
                        "평가손익": st.column_config.NumberColumn(format="%d"),
                    },
                )
            else:
                st.info("보유 종목이 없습니다.")

    st.markdown("---")

    def place(side: str, ticker: str, qty: int, price: float) -> None:
        result = api.buy_order(ticker, qty, price) if side == "BUY" else api.sell_order(ticker, qty, price)
        if result.get("status") == "success":
            add_trade(ticker, "KR", side, price, qty, "수동 주문")
            st.session_state["trade_log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {side} {ticker} x{qty}")
            st.success(f"{side} 주문 완료")
        else:
            st.error(str(result.get("error") or "주문 실패"))

    left, right = st.columns(2)
    with left:
        st.markdown("**매수 주문**")
        buy_code = st.text_input("매수 종목코드", placeholder="005930", key="stock_buy_ticker")
        buy_qty = int(st.number_input("매수 수량", min_value=1, value=1, key="stock_buy_qty"))
        buy_price = float(st.number_input("매수 가격 (0=시장가)", min_value=0, value=0, key="stock_buy_price"))
        if st.button("매수 주문", key="stock_buy_btn", type="primary"):
            place("BUY", buy_code, buy_qty, buy_price)
    with right:
        st.markdown("**매도 주문**")
        sell_code = st.text_input("매도 종목코드", placeholder="005930", key="stock_sell_ticker")
        sell_qty = int(st.number_input("매도 수량", min_value=1, value=1, key="stock_sell_qty"))
        sell_price = float(st.number_input("매도 가격 (0=시장가)", min_value=0, value=0, key="stock_sell_price"))
        if st.button("매도 주문", key="stock_sell_btn", type="primary"):
            place("SELL", sell_code, sell_qty, sell_price)


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

    running = is_running(username, 0)
    left, right = st.columns(2)
    with left:
        if not running and st.button("🚀 AP-1 시작", use_container_width=True, type="primary"):
            start_background_autopilot(
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
            st.rerun()
    with right:
        if running and st.button("🛑 AP-1 중지", use_container_width=True, type="primary"):
            stop_background_autopilot(username, 0)
            st.rerun()

    jobs = get_autopilot_jobs(username)
    job = next((j for j in jobs if int(str(j.get("slot_idx", -1))) == 0), None)
    if job:
        m1, m2, m3 = st.columns(3)
        m1.metric("상태", str(job.get("status", "-")))
        m2.metric("실행 횟수", int(str(job.get("run_count", 0))))
        m3.metric("일간 손익", f"{float(str(job.get('daily_pnl', 0.0))):+.2f}%")

    logs = get_autopilot_logs(username, 0, limit=30)
    if isinstance(logs, pd.DataFrame) and not logs.empty and "message" in logs.columns:
        st.text_area("최근 로그", "\n".join(logs["message"].astype(str).tail(15).tolist()), height=180)
    elif isinstance(logs, list) and logs:
        st.text_area("최근 로그", "\n".join([str(x) for x in logs[-15:]]), height=180)


def render_stock(user: dict[str, object]) -> None:
    _ = (require_auth, inject_pro_css, is_paid, is_pro)
    username = str(user["username"])
    _init_defaults(username)

    st.title("🤖 자동매매 봇")
    st.warning("이 기능은 실제 주문을 실행할 수 있습니다. 반드시 모의투자로 충분히 검증한 뒤 사용하세요.")

    tab_order, tab_auto = st.tabs(["⚡ 주문", "🚀 오토파일럿"])
    with tab_order:
        _render_broker_connect(username)
        st.markdown("---")
        _render_manual_order()
    with tab_auto:
        _render_autopilot(username)

    show_legal_disclaimer()
