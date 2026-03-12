"""
자동매매 봇 페이지
- 한국투자증권 KIS API 연동
- 전략 기반 자동 주문
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime
from trading.kis_api import KISApi
from trading.strategy import AVAILABLE_STRATEGIES
from data.fetcher import fetch_kr_stock
from data.database import add_trade, get_trades
from config.styles import inject_pro_css

st.set_page_config(page_title="자동매매", page_icon="🤖", layout="wide")
inject_pro_css()
st.title("🤖 자동매매 봇")

st.warning(
    "이 기능은 한국투자증권 KIS Open API를 통해 **실제 주식을 매매**합니다. "
    "잘못된 설정으로 인한 손실에 대해 개발자는 책임지지 않습니다. "
    "반드시 **모의투자**로 먼저 테스트하세요."
)

# === KIS API 설정 ===
st.subheader("API 연결 설정")

# 세션 상태 초기화
if "kis_api" not in st.session_state:
    st.session_state["kis_api"] = None
if "auto_trading" not in st.session_state:
    st.session_state["auto_trading"] = False
if "trade_log" not in st.session_state:
    st.session_state["trade_log"] = []

with st.expander("KIS API 키 설정", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        app_key = st.text_input("App Key", type="password", help="한국투자증권에서 발급받은 App Key")
        account_no = st.text_input("계좌번호", help="계좌번호 (예: 5012345601)")
    with col2:
        app_secret = st.text_input("App Secret", type="password", help="한국투자증권에서 발급받은 App Secret")
        trading_mode = st.selectbox("거래 모드", ["모의투자", "실전투자"])

    base_url = (
        "https://openapivts.koreainvestment.com:29443"
        if trading_mode == "모의투자"
        else "https://openapi.koreainvestment.com:9443"
    )

    if st.button("API 연결", type="primary"):
        if app_key and app_secret and account_no:
            try:
                api = KISApi(app_key, app_secret, account_no, base_url)
                api.get_access_token()
                st.session_state["kis_api"] = api
                st.success(f"API 연결 성공! (모드: {trading_mode})")
            except Exception as e:
                st.error(f"연결 실패: {e}")
        else:
            st.error("모든 필드를 입력하세요.")

st.markdown("---")

# === API 상태 표시 ===
api = st.session_state.get("kis_api")
if api:
    status = api.get_status()
    col1, col2, col3 = st.columns(3)
    col1.metric("연결 상태", "연결됨" if status["has_token"] else "미연결")
    col2.metric("거래 모드", trading_mode)
    col3.metric("계좌", status["account"])

    st.markdown("---")

    # === 잔고 조회 ===
    st.subheader("잔고 조회")
    if st.button("잔고 새로고침"):
        with st.spinner("잔고 조회 중..."):
            balance = api.get_balance()
            if "error" in balance:
                st.error(f"잔고 조회 실패: {balance['error']}")
            else:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("총 평가금액", f"{balance.get('총평가금액', 0):,}원")
                col2.metric("총 매입금액", f"{balance.get('총매입금액', 0):,}원")
                col3.metric("총 평가손익", f"{balance.get('총평가손익', 0):,}원")
                col4.metric("예수금", f"{balance.get('예수금', 0):,}원")

                holdings = balance.get("holdings", [])
                if holdings:
                    st.dataframe(pd.DataFrame(holdings), use_container_width=True)
                else:
                    st.info("보유 종목이 없습니다.")

    st.markdown("---")

    # === 수동 주문 ===
    st.subheader("수동 주문")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**매수 주문**")
        buy_ticker = st.text_input("매수 종목코드", key="buy_ticker", placeholder="005930")
        buy_qty = st.number_input("매수 수량", min_value=1, value=1, key="buy_qty")
        buy_price = st.number_input("매수 가격 (0=시장가)", min_value=0, value=0, key="buy_price")
        if st.button("매수 주문", type="primary", key="btn_buy"):
            with st.spinner("매수 주문 중..."):
                result = api.buy_order(buy_ticker, buy_qty, buy_price)
                if result.get("status") == "success":
                    st.success(f"매수 완료: {result.get('message')}")
                    add_trade(buy_ticker, "KR", "BUY", buy_price, buy_qty, "수동 매수")
                    st.session_state["trade_log"].append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] 매수: {buy_ticker} x {buy_qty}"
                    )
                else:
                    st.error(f"매수 실패: {result.get('error')}")

    with col2:
        st.markdown("**매도 주문**")
        sell_ticker = st.text_input("매도 종목코드", key="sell_ticker", placeholder="005930")
        sell_qty = st.number_input("매도 수량", min_value=1, value=1, key="sell_qty")
        sell_price = st.number_input("매도 가격 (0=시장가)", min_value=0, value=0, key="sell_price")
        if st.button("매도 주문", type="primary", key="btn_sell"):
            with st.spinner("매도 주문 중..."):
                result = api.sell_order(sell_ticker, sell_qty, sell_price)
                if result.get("status") == "success":
                    st.success(f"매도 완료: {result.get('message')}")
                    add_trade(sell_ticker, "KR", "SELL", sell_price, sell_qty, "수동 매도")
                    st.session_state["trade_log"].append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] 매도: {sell_ticker} x {sell_qty}"
                    )
                else:
                    st.error(f"매도 실패: {result.get('error')}")

    st.markdown("---")

    # === 전략 기반 자동매매 ===
    st.subheader("전략 기반 자동매매")

    col1, col2 = st.columns(2)
    with col1:
        auto_ticker = st.text_input("감시 종목코드", value="005930", key="auto_ticker")
        strategy_name = st.selectbox("매매 전략", list(AVAILABLE_STRATEGIES.keys()))
        auto_qty = st.number_input("1회 매매 수량", min_value=1, value=1, key="auto_qty")

    with col2:
        st.markdown("**전략 설명**")
        strategy_class = AVAILABLE_STRATEGIES[strategy_name]
        strategy_instance = strategy_class()
        st.json(strategy_instance.params)

    # 현재 시그널 확인
    if st.button("현재 시그널 확인", use_container_width=True):
        with st.spinner("시그널 분석 중..."):
            df = fetch_kr_stock(auto_ticker, period="3mo")
            if df.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                strategy = strategy_class()
                signal = strategy.get_signal(df)
                if signal == "BUY":
                    st.success(f"현재 시그널: **매수 (BUY)** - {strategy.name}")
                elif signal == "SELL":
                    st.error(f"현재 시그널: **매도 (SELL)** - {strategy.name}")
                else:
                    st.info(f"현재 시그널: **관망 (HOLD)** - {strategy.name}")

                current_price_data = api.get_price(auto_ticker)
                if "error" not in current_price_data:
                    st.metric("현재가", f"{current_price_data['현재가']:,}원",
                              f"{current_price_data['등락률']:+.2f}%")

    st.markdown("---")

    st.subheader("자동매매 스케줄러")

    if "scheduler_running" not in st.session_state:
        st.session_state["scheduler_running"] = False
    if "scheduler_last_run" not in st.session_state:
        st.session_state["scheduler_last_run"] = None
    if "scheduler_run_count" not in st.session_state:
        st.session_state["scheduler_run_count"] = 0

    sched_col1, sched_col2, sched_col3 = st.columns(3)
    with sched_col1:
        interval_map = {"1분": 60, "5분": 300, "15분": 900, "30분": 1800, "1시간": 3600}
        interval_label = st.selectbox("실행 간격", list(interval_map.keys()), index=1, key="sched_interval")
        interval_sec = interval_map[interval_label]
    with sched_col2:
        max_runs = st.number_input("최대 실행 횟수 (0=무제한)", min_value=0, value=0, step=1, key="sched_max_runs")
    with sched_col3:
        st.metric("실행 횟수", st.session_state["scheduler_run_count"])
        if st.session_state["scheduler_last_run"]:
            st.caption(f"마지막: {st.session_state['scheduler_last_run']}")

    sched_btn_col1, sched_btn_col2 = st.columns(2)
    with sched_btn_col1:
        if st.button(
            "스케줄러 중지" if st.session_state["scheduler_running"] else "스케줄러 시작",
            type="primary", use_container_width=True, key="sched_toggle"
        ):
            st.session_state["scheduler_running"] = not st.session_state["scheduler_running"]
            if not st.session_state["scheduler_running"]:
                st.session_state["scheduler_run_count"] = 0
            st.rerun()
    with sched_btn_col2:
        if st.button("카운트 초기화", use_container_width=True, key="sched_reset"):
            st.session_state["scheduler_run_count"] = 0
            st.rerun()

    if st.session_state["scheduler_running"]:
        import time as _time

        if max_runs > 0 and st.session_state["scheduler_run_count"] >= max_runs:
            st.session_state["scheduler_running"] = False
            st.warning(f"최대 실행 횟수({max_runs}회) 도달. 스케줄러 중지.")
        else:
            st.success(f"스케줄러 동작 중 | 간격: {interval_label} | 다음 실행까지 대기 중...")

            df = fetch_kr_stock(auto_ticker, period="3mo")
            if not df.empty:
                strategy = strategy_class()
                signal = strategy.get_signal(df)
                now_str = datetime.now().strftime("%H:%M:%S")

                if signal == "BUY":
                    result = api.buy_order(auto_ticker, auto_qty, 0)
                    log_msg = f"[{now_str}] AUTO BUY: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                    st.session_state["trade_log"].append(log_msg)
                    if result.get("status") == "success":
                        add_trade(auto_ticker, "KR", "BUY", 0, auto_qty, f"스케줄러 매수 ({strategy.name})")
                elif signal == "SELL":
                    result = api.sell_order(auto_ticker, auto_qty, 0)
                    log_msg = f"[{now_str}] AUTO SELL: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                    st.session_state["trade_log"].append(log_msg)
                    if result.get("status") == "success":
                        add_trade(auto_ticker, "KR", "SELL", 0, auto_qty, f"스케줄러 매도 ({strategy.name})")
                else:
                    st.session_state["trade_log"].append(f"[{now_str}] AUTO HOLD: {auto_ticker} ({strategy.name})")

                st.session_state["scheduler_run_count"] += 1
                st.session_state["scheduler_last_run"] = now_str

            _time.sleep(interval_sec)
            st.rerun()

    st.markdown("---")

    st.subheader("거래 로그")
    if st.session_state["trade_log"]:
        for log in reversed(st.session_state["trade_log"][-20:]):
            st.text(log)
    else:
        st.info("거래 로그가 없습니다.")

    # 거래 이력 (DB)
    with st.expander("전체 거래 이력 (DB)"):
        trades_df = get_trades(limit=50)
        if not trades_df.empty:
            st.dataframe(trades_df, use_container_width=True)
        else:
            st.info("거래 이력이 없습니다.")

else:
    st.info("위에서 KIS API 키를 입력하고 연결하세요.")
    st.markdown("""
    ### KIS API 키 발급 방법
    1. [한국투자증권](https://securities.koreainvestment.com) 접속
    2. 계좌 개설 후 Open API 신청
    3. API Key / Secret 발급
    4. 모의투자 계좌 개설 (테스트용)

    자세한 내용은 [KIS Developers](https://apiportal.koreainvestment.com) 를 참조하세요.
    """)
