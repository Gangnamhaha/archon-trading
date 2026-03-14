import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime
from trading.kis_api import KISApi
from trading.kiwoom_api import KiwoomApi
from trading.nh_api import NHApi
from trading.strategy import AVAILABLE_STRATEGIES
from data.fetcher import fetch_kr_stock
from data.database import add_trade, get_trades
from config.styles import inject_pro_css
from config.auth import require_pro

st.set_page_config(page_title="자동매매", page_icon="🤖", layout="wide")
require_pro()
inject_pro_css()
st.title("🤖 자동매매 봇")

st.warning(
    "이 기능은 증권사 API를 통해 **실제 주식을 매매**합니다. "
    "잘못된 설정으로 인한 손실에 대해 개발자는 책임지지 않습니다. "
    "반드시 **모의투자**로 먼저 테스트하세요."
)

st.subheader("API 연결 설정")

if "broker_api" not in st.session_state:
    st.session_state["broker_api"] = None
if "broker_name" not in st.session_state:
    st.session_state["broker_name"] = None
if "auto_trading" not in st.session_state:
    st.session_state["auto_trading"] = False
if "trade_log" not in st.session_state:
    st.session_state["trade_log"] = []

BROKER_OPTIONS = {
    "한국투자증권 (KIS)": "KIS",
    "키움증권": "KIWOOM",
    "NH투자증권": "NH",
}

with st.expander("증권사 API 설정", expanded=True):
    broker_label = st.selectbox("증권사 선택", list(BROKER_OPTIONS.keys()))
    broker_code = BROKER_OPTIONS[broker_label]

    if broker_code == "NH":
        st.error(
            "⚠️ NH투자증권은 REST API를 제공하지 않습니다. "
            "QV Open API (Windows COM)만 지원되어 웹 환경에서는 사용할 수 없습니다."
        )
    else:
        col1, col2 = st.columns(2)
        with col1:
            app_key = st.text_input("App Key", type="password", key="broker_app_key")
            account_no = st.text_input("계좌번호", key="broker_account")
        with col2:
            app_secret = st.text_input(
                "Secret Key" if broker_code == "KIWOOM" else "App Secret",
                type="password",
                key="broker_secret",
            )
            trading_mode = st.selectbox("거래 모드", ["모의투자", "실전투자"])

        if broker_code == "KIS":
            base_url = (
                "https://openapivts.koreainvestment.com:29443"
                if trading_mode == "모의투자"
                else "https://openapi.koreainvestment.com:9443"
            )
        else:
            base_url = (
                "https://mockapi.kiwoom.com"
                if trading_mode == "모의투자"
                else "https://api.kiwoom.com"
            )

        if st.button("API 연결", type="primary"):
            if app_key and app_secret and account_no:
                try:
                    if broker_code == "KIS":
                        api = KISApi(app_key, app_secret, account_no, base_url)
                    else:
                        api = KiwoomApi(app_key, app_secret, account_no, base_url)
                    api.get_access_token()
                    st.session_state["broker_api"] = api
                    st.session_state["broker_name"] = broker_label
                    st.success(f"{broker_label} API 연결 성공! (모드: {trading_mode})")
                except Exception as e:
                    st.error(f"연결 실패: {e}")
            else:
                st.error("모든 필드를 입력하세요.")

st.markdown("---")

api = st.session_state.get("broker_api")
connected_broker = st.session_state.get("broker_name", "")

if api:
    status = api.get_status()
    col1, col2, col3 = st.columns(3)
    col1.metric("연결 상태", "연결됨" if status["has_token"] else "미연결")
    col2.metric("증권사", connected_broker)
    col3.metric("계좌", status["account"])

    st.markdown("---")

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

    st.subheader("전략 기반 자동매매")

    trade_mode = st.radio("매매 모드", ["전략 기반", "적립식 매수 (DCA)"], horizontal=True, key="trade_mode")

    col1, col2 = st.columns(2)
    with col1:
        auto_ticker = st.text_input("감시 종목코드", value="005930", key="auto_ticker")
        if trade_mode == "전략 기반":
            strategy_name = st.selectbox("매매 전략", list(AVAILABLE_STRATEGIES.keys()))
        auto_qty = st.number_input("1회 매매 수량", min_value=1, value=1, key="auto_qty")

    with col2:
        if trade_mode == "전략 기반":
            strategy_class = AVAILABLE_STRATEGIES[strategy_name]
            strategy_instance = strategy_class()
            st.json(strategy_instance.params)
        else:
            st.markdown("**DCA 설정**")
            st.caption("정해진 간격으로 동일 금액/수량을 자동 매수하여 평균 매입단가를 낮춥니다.")

    st.markdown("##### 리스크 관리")
    risk_col1, risk_col2, risk_col3 = st.columns(3)
    with risk_col1:
        stop_loss_pct = st.number_input("손절 (%) — 0=미사용", min_value=0.0, max_value=50.0, value=0.0, step=0.5, key="stop_loss")
    with risk_col2:
        take_profit_pct = st.number_input("익절 (%) — 0=미사용", min_value=0.0, max_value=100.0, value=0.0, step=1.0, key="take_profit")
    with risk_col3:
        trailing_stop = st.checkbox("트레일링 스탑", value=False, key="trailing_stop",
                                     help="최고점 대비 손절% 하락 시 자동 매도")

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
                now_str = datetime.now().strftime("%H:%M:%S")
                current_price = float(df["Close"].iloc[-1])

                sl_triggered = False
                tp_triggered = False
                if stop_loss_pct > 0 or take_profit_pct > 0:
                    buy_avg = st.session_state.get("auto_buy_avg", 0)
                    peak_price = st.session_state.get("auto_peak_price", current_price)
                    if current_price > peak_price:
                        st.session_state["auto_peak_price"] = current_price
                        peak_price = current_price
                    if buy_avg > 0:
                        pnl_pct = (current_price / buy_avg - 1) * 100
                        if stop_loss_pct > 0:
                            ref = peak_price if trailing_stop else buy_avg
                            loss = (current_price / ref - 1) * 100
                            if loss <= -stop_loss_pct:
                                sl_triggered = True
                        if take_profit_pct > 0 and pnl_pct >= take_profit_pct:
                            tp_triggered = True

                if sl_triggered or tp_triggered:
                    reason = "손절" if sl_triggered else "익절"
                    result = api.sell_order(auto_ticker, auto_qty, 0)
                    log_msg = f"[{now_str}] AUTO {reason}: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                    st.session_state["trade_log"].append(log_msg)
                    if result.get("status") == "success":
                        add_trade(auto_ticker, "KR", "SELL", 0, auto_qty, f"스케줄러 {reason}")
                    st.session_state["auto_buy_avg"] = 0
                elif trade_mode == "적립식 매수 (DCA)":
                    result = api.buy_order(auto_ticker, auto_qty, 0)
                    log_msg = f"[{now_str}] DCA BUY: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                    st.session_state["trade_log"].append(log_msg)
                    if result.get("status") == "success":
                        add_trade(auto_ticker, "KR", "BUY", 0, auto_qty, "DCA 적립식 매수")
                        prev_avg = st.session_state.get("auto_buy_avg", 0)
                        prev_cnt = st.session_state.get("auto_buy_cnt", 0)
                        st.session_state["auto_buy_avg"] = (prev_avg * prev_cnt + current_price) / (prev_cnt + 1)
                        st.session_state["auto_buy_cnt"] = prev_cnt + 1
                else:
                    strategy = strategy_class()
                    signal = strategy.get_signal(df)
                    if signal == "BUY":
                        result = api.buy_order(auto_ticker, auto_qty, 0)
                        log_msg = f"[{now_str}] AUTO BUY: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                        st.session_state["trade_log"].append(log_msg)
                        if result.get("status") == "success":
                            add_trade(auto_ticker, "KR", "BUY", 0, auto_qty, f"스케줄러 매수 ({strategy.name})")
                            st.session_state["auto_buy_avg"] = current_price
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

    # ===================================================================
    # 오토파일럿 모드
    # ===================================================================
    st.subheader("🚀 오토파일럿 모드")
    st.caption("AI가 종목 추천 → 자동 선택 → 포지션 사이징 → 매수/매도를 모두 자동 수행합니다.")

    if "autopilot_running" not in st.session_state:
        st.session_state["autopilot_running"] = False
    if "autopilot_holdings" not in st.session_state:
        st.session_state["autopilot_holdings"] = {}

    with st.expander("오토파일럿 설정", expanded=not st.session_state["autopilot_running"]):
        ap_col1, ap_col2 = st.columns(2)
        with ap_col1:
            ap_capital = st.number_input("투자금 (원)", min_value=100_000, value=1_000_000, step=100_000, key="ap_capital", format="%d")
            ap_market = st.selectbox("시장", ["KOSPI", "KOSDAQ"], key="ap_market")
            ap_mode = st.selectbox("추천 모드", ["일반 추천", "🔥 공격적 추천"], key="ap_mode")
        with ap_col2:
            ap_max_stocks = st.slider("최대 보유 종목 수", 1, 10, 5, key="ap_max_stocks")
            ap_max_per_stock = st.slider("종목당 최대 비중 (%)", 10, 50, 20, key="ap_max_per_stock")
            ap_stop_loss = st.slider("종목별 손절선 (%)", 1, 20, 5, key="ap_stop_loss")
        ap_col3, ap_col4 = st.columns(2)
        with ap_col3:
            ap_take_profit = st.slider("종목별 익절선 (%)", 5, 50, 15, key="ap_take_profit")
        with ap_col4:
            ap_daily_loss_limit = st.slider("일일 최대 손실 한도 (%)", 1, 20, 5, key="ap_daily_limit")

        st.warning(
            f"⚠️ 투자금 {ap_capital:,}원 중 최대 {ap_max_stocks}종목에 분배 투자합니다. "
            f"종목당 최대 {ap_max_per_stock}%, 손절 -{ap_stop_loss}%, 익절 +{ap_take_profit}%. "
            f"일일 손실이 -{ap_daily_loss_limit}% 도달 시 전체 자동 중지됩니다."
        )

    ap_btn_col1, ap_btn_col2 = st.columns(2)
    with ap_btn_col1:
        if st.button(
            "🛑 오토파일럿 중지" if st.session_state["autopilot_running"] else "🚀 오토파일럿 시작",
            type="primary", use_container_width=True, key="ap_toggle"
        ):
            st.session_state["autopilot_running"] = not st.session_state["autopilot_running"]
            if not st.session_state["autopilot_running"]:
                st.success("오토파일럿이 중지되었습니다.")
            st.rerun()
    with ap_btn_col2:
        if st.button("📊 1회 스캔 (테스트)", use_container_width=True, key="ap_scan_once"):
            with st.spinner("AI 종목 스캔 중..."):
                try:
                    if ap_mode == "🔥 공격적 추천":
                        from analysis.recommender import recommend_aggressive_stocks
                        scan_df = recommend_aggressive_stocks(market=ap_market, top_n=100, result_count=ap_max_stocks)
                        score_col = "공격점수"
                    else:
                        from analysis.recommender import recommend_stocks
                        scan_df = recommend_stocks(market=ap_market, top_n=50, result_count=ap_max_stocks)
                        score_col = "종합점수"

                    if scan_df.empty:
                        st.error("스캔 결과가 없습니다.")
                    else:
                        st.success(f"{len(scan_df)}개 종목 발견")

                        per_stock_capital = int(ap_capital / len(scan_df))
                        plan_data = []
                        for _, row in scan_df.iterrows():
                            price = int(row["현재가"])
                            qty = max(1, per_stock_capital // price) if price > 0 else 0
                            alloc_pct = round(qty * price / ap_capital * 100, 1)
                            plan_data.append({
                                "종목코드": row["종목코드"],
                                "종목명": row["종목명"],
                                "현재가": f"{price:,}",
                                "점수": round(row[score_col], 1),
                                "매수수량": qty,
                                "투자금": f"{qty * price:,}",
                                "비중(%)": alloc_pct,
                                "손절가": f"{int(price * (1 - ap_stop_loss / 100)):,}",
                                "익절가": f"{int(price * (1 + ap_take_profit / 100)):,}",
                            })
                        plan_df = pd.DataFrame(plan_data)
                        st.dataframe(plan_df, use_container_width=True, hide_index=True)

                        total_invest = sum(int(r["투자금"].replace(",", "")) for r in plan_data)
                        remaining = ap_capital - total_invest
                        ic1, ic2, ic3 = st.columns(3)
                        ic1.metric("총 투자금", f"{total_invest:,}원")
                        ic2.metric("잔여 현금", f"{remaining:,}원")
                        ic3.metric("투자 종목", f"{len(plan_data)}개")
                except Exception as e:
                    st.error(f"스캔 실패: {e}")

    if st.session_state["autopilot_running"]:
        import time as _ap_time

        st.success("🚀 오토파일럿 동작 중...")

        try:
            if ap_mode == "🔥 공격적 추천":
                from analysis.recommender import recommend_aggressive_stocks
                scan_df = recommend_aggressive_stocks(market=ap_market, top_n=100, result_count=ap_max_stocks)
                score_col = "공격점수"
            else:
                from analysis.recommender import recommend_stocks
                scan_df = recommend_stocks(market=ap_market, top_n=50, result_count=ap_max_stocks)
                score_col = "종합점수"

            if not scan_df.empty:
                now_str = datetime.now().strftime("%H:%M:%S")
                holdings = st.session_state.get("autopilot_holdings", {})
                daily_pnl = 0.0

                for _, row in scan_df.iterrows():
                    ticker = row["종목코드"]
                    price = int(row["현재가"])

                    if ticker in holdings:
                        entry = holdings[ticker]
                        pnl_pct = (price / entry["avg_price"] - 1) * 100
                        daily_pnl += pnl_pct * entry["qty"] * entry["avg_price"] / ap_capital * 100

                        if pnl_pct <= -ap_stop_loss:
                            result = api.sell_order(ticker, entry["qty"], 0)
                            log_msg = f"[{now_str}] AP 손절: {row['종목명']} {pnl_pct:+.1f}% → {result.get('status', 'unknown')}"
                            st.session_state["trade_log"].append(log_msg)
                            if result.get("status") == "success":
                                add_trade(ticker, "KR", "SELL", 0, entry["qty"], f"오토파일럿 손절 ({pnl_pct:+.1f}%)")
                            del holdings[ticker]
                        elif pnl_pct >= ap_take_profit:
                            result = api.sell_order(ticker, entry["qty"], 0)
                            log_msg = f"[{now_str}] AP 익절: {row['종목명']} {pnl_pct:+.1f}% → {result.get('status', 'unknown')}"
                            st.session_state["trade_log"].append(log_msg)
                            if result.get("status") == "success":
                                add_trade(ticker, "KR", "SELL", 0, entry["qty"], f"오토파일럿 익절 ({pnl_pct:+.1f}%)")
                            del holdings[ticker]
                    else:
                        if len(holdings) < ap_max_stocks:
                            per_stock = int(ap_capital * ap_max_per_stock / 100)
                            qty = max(1, per_stock // price) if price > 0 else 0
                            if qty > 0:
                                result = api.buy_order(ticker, qty, 0)
                                log_msg = f"[{now_str}] AP 매수: {row['종목명']} x{qty} @{price:,} → {result.get('status', 'unknown')}"
                                st.session_state["trade_log"].append(log_msg)
                                if result.get("status") == "success":
                                    add_trade(ticker, "KR", "BUY", price, qty, f"오토파일럿 매수 (점수:{row[score_col]:+.1f})")
                                    holdings[ticker] = {"avg_price": price, "qty": qty, "name": row["종목명"]}

                st.session_state["autopilot_holdings"] = holdings

                daily_loss_pct = daily_pnl
                if daily_loss_pct <= -ap_daily_loss_limit:
                    st.session_state["autopilot_running"] = False
                    st.error(f"⚠️ 일일 손실 한도 도달 ({daily_loss_pct:.1f}%). 오토파일럿 자동 중지.")
                    for t, h in list(holdings.items()):
                        api.sell_order(t, h["qty"], 0)
                        st.session_state["trade_log"].append(f"[{now_str}] AP 긴급매도: {h['name']} x{h['qty']}")
                    st.session_state["autopilot_holdings"] = {}

                if holdings:
                    st.markdown("##### 현재 오토파일럿 보유 종목")
                    hold_data = []
                    for t, h in holdings.items():
                        current = api.get_price(t)
                        cur_price = current.get("현재가", h["avg_price"]) if "error" not in current else h["avg_price"]
                        pnl = (cur_price / h["avg_price"] - 1) * 100
                        hold_data.append({
                            "종목명": h["name"], "매수가": f"{h['avg_price']:,}",
                            "현재가": f"{cur_price:,}", "수량": h["qty"],
                            "수익률(%)": f"{pnl:+.1f}",
                        })
                    st.dataframe(pd.DataFrame(hold_data), use_container_width=True, hide_index=True)
            else:
                st.session_state["trade_log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] AP: 스캔 결과 없음")

        except Exception as e:
            st.session_state["trade_log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] AP 오류: {e}")
            st.error(f"오토파일럿 오류: {e}")

        _ap_time.sleep(300)
        st.rerun()

    st.markdown("---")

    st.subheader("🤖 AI 트레이딩 어시스턴트")
    st.caption("자연어로 오토파일럿을 제어하세요. 예: '손절을 3%로 바꿔줘', '종목 수를 3개로 줄여', '공격적 모드로 전환'")

    if "ap_chat_messages" not in st.session_state:
        st.session_state["ap_chat_messages"] = []
    if "ap_openai_key" not in st.session_state:
        st.session_state["ap_openai_key"] = ""

    ap_api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state["ap_openai_key"], key="ap_ai_key")
    if ap_api_key:
        st.session_state["ap_openai_key"] = ap_api_key

    if not ap_api_key:
        st.info("OpenAI API Key를 입력하면 AI 어시스턴트를 사용할 수 있습니다.")
    else:
        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state["ap_chat_messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        if user_msg := st.chat_input("오토파일럿에게 명령하세요...", key="ap_chat_input"):
            st.session_state["ap_chat_messages"].append({"role": "user", "content": user_msg})

            _ap_system = (
                "당신은 Archon 오토파일럿 트레이딩 AI 어시스턴트입니다. 한국어로 답변하세요.\n"
                "사용자가 오토파일럿 설정을 변경하라고 요청하면, 정확한 JSON 명령을 응답에 포함하세요.\n"
                "JSON 형식: {\"action\": \"update_config\", \"changes\": {\"key\": value}}\n"
                "변경 가능한 키: ap_capital(투자금), ap_market(KOSPI/KOSDAQ), ap_mode(일반 추천/공격적 추천), "
                "ap_max_stocks(최대종목수 1-10), ap_max_per_stock(종목당비중 10-50%), "
                "ap_stop_loss(손절 1-20%), ap_take_profit(익절 5-50%), ap_daily_limit(일일손실한도 1-20%)\n"
                "다른 키: ap_start(오토파일럿 시작), ap_stop(오토파일럿 중지)\n\n"
                f"현재 설정: 투자금={ap_capital:,}원, 시장={ap_market}, 모드={ap_mode}, "
                f"최대종목={ap_max_stocks}, 종목당비중={ap_max_per_stock}%, "
                f"손절={ap_stop_loss}%, 익절={ap_take_profit}%, 일일한도={ap_daily_loss_limit}%\n"
                f"오토파일럿 상태: {'동작중' if st.session_state['autopilot_running'] else '중지'}\n"
                f"현재 보유종목: {len(st.session_state.get('autopilot_holdings', {}))}개\n\n"
                "설정 변경이 아닌 일반 투자 질문에도 친절하게 답변하세요.\n"
                "설정 변경 시 반드시 변경 내용을 확인하는 문장도 포함하세요."
            )

            try:
                from openai import OpenAI
                import json as _json
                client = OpenAI(api_key=ap_api_key)

                _messages = [{"role": "system", "content": _ap_system}]
                for m in st.session_state["ap_chat_messages"]:
                    _messages.append({"role": m["role"], "content": m["content"]})

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=_messages,
                    temperature=0.3,
                    max_tokens=1024,
                )
                reply = response.choices[0].message.content
                st.session_state["ap_chat_messages"].append({"role": "assistant", "content": reply})

                if "{\"action\"" in reply:
                    try:
                        json_start = reply.index("{\"action\"")
                        json_end = reply.index("}", json_start) + 1
                        cmd = _json.loads(reply[json_start:json_end])
                        if cmd.get("action") == "update_config":
                            for k, v in cmd.get("changes", {}).items():
                                if k == "ap_start":
                                    st.session_state["autopilot_running"] = True
                                elif k == "ap_stop":
                                    st.session_state["autopilot_running"] = False
                                elif k in ("ap_capital", "ap_max_stocks", "ap_max_per_stock",
                                           "ap_stop_loss", "ap_take_profit", "ap_daily_limit"):
                                    st.session_state[k] = v
                                elif k == "ap_market":
                                    st.session_state["ap_market"] = v
                                elif k == "ap_mode":
                                    st.session_state["ap_mode"] = v
                    except (ValueError, _json.JSONDecodeError):
                        pass

            except Exception as e:
                error_reply = f"오류가 발생했습니다: {e}"
                st.session_state["ap_chat_messages"].append({"role": "assistant", "content": error_reply})

            st.rerun()

    st.markdown("---")

    st.subheader("거래 로그")
    if st.session_state["trade_log"]:
        for log in reversed(st.session_state["trade_log"][-20:]):
            st.text(log)
    else:
        st.info("거래 로그가 없습니다.")

    with st.expander("전체 거래 이력 (DB)"):
        trades_df = get_trades(limit=50)
        if not trades_df.empty:
            st.dataframe(trades_df, use_container_width=True)
        else:
            st.info("거래 이력이 없습니다.")

else:
    st.info("위에서 증권사를 선택하고 API 키를 입력한 뒤 연결하세요.")
    st.markdown("""
    ### 증권사별 API 안내

    **한국투자증권 (KIS)**
    1. [한국투자증권](https://securities.koreainvestment.com) 접속
    2. 계좌 개설 후 Open API 신청 → [KIS Developers](https://apiportal.koreainvestment.com)
    3. App Key / Secret 발급, 모의투자 계좌 개설

    **키움증권**
    1. [키움증권](https://www.kiwoom.com) 접속
    2. 계좌 개설 후 Open API 신청 → [키움 Open API](https://api.kiwoom.com)
    3. App Key / Secret Key 발급

    **NH투자증권**
    - REST API 미지원 (QV Open API: Windows COM 전용)
    - 웹 환경에서는 사용할 수 없습니다.
    """)
