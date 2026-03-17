import sys
import os
import importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
from trading.kis_api import KISApi, market_status_text
from trading.kiwoom_api import KiwoomApi
from trading.nh_api import NHApi
from trading.strategy import AVAILABLE_STRATEGIES
from data.fetcher import fetch_kr_stock, fetch_us_stock, get_us_popular_stocks
from data.database import add_trade, get_trades, get_autopilot_jobs, get_autopilot_logs

_ap_engine = None
try:
    import trading.autopilot_engine as _ap_engine
except Exception:
    _ap_engine = None

_AP_ENGINE_OK = _ap_engine is not None


def start_background_autopilot(username: str, slot_idx: int, **kwargs) -> bool:
    if _ap_engine is None:
        return False
    return bool(_ap_engine.start_background_autopilot(username, slot_idx, **kwargs))


def stop_background_autopilot(username: str, slot_idx: int) -> None:
    if _ap_engine is None:
        return
    _ap_engine.stop_background_autopilot(username, slot_idx)


def stop_all_background_autopilots(username: str) -> None:
    if _ap_engine is None:
        return
    _ap_engine.stop_all_background_autopilots(username)


def ap_is_running(username: str, slot_idx: int) -> bool:
    if _ap_engine is None:
        return False
    return bool(_ap_engine.is_running(username, slot_idx))


def ap_running_count(username: str) -> int:
    if _ap_engine is None:
        return 0
    return int(_ap_engine.get_running_count(username))
from config.styles import inject_pro_css, load_user_preferences, require_plan, save_user_preferences, show_legal_disclaimer
from config.auth import require_auth

st.set_page_config(page_title="자동매매", page_icon="🤖", layout="wide")
user = require_auth()
username = user["username"]
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

autopilot_defaults = {
    "ap_capital": 1_000_000,
    "ap_market": "KOSPI",
    "ap_mode": "일반 추천",
    "ap_max_stocks": 5,
    "ap_max_per_stock": 20,
    "ap_stop_loss": 5,
    "ap_take_profit": 15,
    "ap_daily_limit": 5,
}
autopilot_saved = load_user_preferences(username, "autopilot")
for key, default in autopilot_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = autopilot_saved.get(key, default)


def _recommend_us_stocks(top_n: int = 40, result_count: int = 5, aggressive: bool = False) -> pd.DataFrame:
    us_df = get_us_popular_stocks().head(top_n)
    results = []
    for _, row in us_df.iterrows():
        ticker = str(row["ticker"])
        name = str(row["name"])
        df = fetch_us_stock(ticker, period="6mo")
        if df.empty or len(df) < 30:
            continue

        close = pd.Series(df["Close"])
        ret_1d = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2) if len(close) >= 2 else 0.0
        ret_5d = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else 0.0
        ret_20d = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else 0.0

        volume = pd.Series(df["Volume"]) if "Volume" in df.columns else pd.Series(dtype=float)
        vol_ratio = 1.0
        if not volume.empty and len(volume) >= 20:
            rolling_mean = pd.Series(volume.rolling(20).mean()).dropna()
            avg_vol = float(rolling_mean.tail(1).values[0]) if not rolling_mean.empty else 0.0
            if avg_vol > 0 and len(volume) > 0:
                vol_ratio = float(volume.tail(1).values[0] / avg_vol)

        returns = close.pct_change().dropna()
        annual_vol = float(returns.tail(20).std() * (252 ** 0.5) * 100) if len(returns) >= 20 else 0.0

        if aggressive:
            score = ret_20d * 1.8 + ret_5d * 0.8 + max(0.0, (vol_ratio - 1.0) * 10.0) + annual_vol * 0.2
            score = max(-50.0, min(100.0, score))
            results.append(
                {
                    "종목코드": ticker,
                    "종목명": name,
                    "현재가": int(float(close.iloc[-1])),
                    "1일(%)": ret_1d,
                    "5일(%)": ret_5d,
                    "20일(%)": ret_20d,
                    "거래량비율": round(vol_ratio, 2),
                    "변동성(%)": round(annual_vol, 1),
                    "공격점수": round(score, 1),
                }
            )
        else:
            score = ret_20d * 1.2 + ret_5d * 0.8 + ret_1d * 0.4 + max(0.0, (vol_ratio - 1.0) * 5.0)
            score = max(-100.0, min(100.0, score))
            recommendation = "강력 매수" if score >= 25 else "매수" if score >= 10 else "관망"
            results.append(
                {
                    "종목코드": ticker,
                    "종목명": name,
                    "현재가": int(float(close.iloc[-1])),
                    "1일(%)": ret_1d,
                    "5일(%)": ret_5d,
                    "20일(%)": ret_20d,
                    "종합점수": round(score, 1),
                    "추천": recommendation,
                }
            )

    if not results:
        return pd.DataFrame()

    score_col = "공격점수" if aggressive else "종합점수"
    return pd.DataFrame(results).sort_values(score_col, ascending=False).head(result_count).reset_index(drop=True)

BROKER_OPTIONS = {
    "한국투자증권 (KIS)": "KIS",
    "키움증권": "KIWOOM",
    "NH투자증권": "NH",
}

_broker_saved = load_user_preferences(username, "broker_api")
if "broker_app_key" not in st.session_state and _broker_saved:
    st.session_state["broker_app_key"] = _broker_saved.get("app_key", "")
    st.session_state["broker_secret"] = _broker_saved.get("app_secret", "")
    st.session_state["broker_account"] = _broker_saved.get("account_no", "")
    st.session_state["_saved_broker"] = _broker_saved.get("broker", "")
    st.session_state["_saved_mode"] = _broker_saved.get("trading_mode", "모의투자")

_saved_broker_label = None
if st.session_state.get("_saved_broker"):
    for lbl, code in BROKER_OPTIONS.items():
        if code == st.session_state["_saved_broker"]:
            _saved_broker_label = lbl
            break

with st.expander("증권사 API 설정", expanded=True):
    _broker_labels = list(BROKER_OPTIONS.keys())
    _default_idx = _broker_labels.index(_saved_broker_label) if _saved_broker_label in _broker_labels else 0
    broker_label = str(st.selectbox("증권사 선택", _broker_labels, index=_default_idx) or _broker_labels[0])
    broker_code = BROKER_OPTIONS[broker_label]

    if broker_code == "NH":
        st.error(
            "⚠️ NH투자증권은 REST API를 제공하지 않습니다. "
            "QV Open API (Windows COM)만 지원되어 웹 환경에서는 사용할 수 없습니다."
        )
    else:
        _mode_options = ["모의투자", "실전투자"]
        _default_mode = _mode_options.index(st.session_state.get("_saved_mode", "모의투자")) if st.session_state.get("_saved_mode") in _mode_options else 0
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
            trading_mode = st.selectbox("거래 모드", _mode_options, index=_default_mode)

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
                    save_user_preferences(username, "broker_api", {
                        "broker": broker_code,
                        "app_key": app_key,
                        "app_secret": app_secret,
                        "account_no": account_no,
                        "trading_mode": trading_mode,
                    })
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
    _bal_col1, _bal_col2 = st.columns([1, 1])
    with _bal_col1:
        _show_debug = st.checkbox("🔍 API 응답 디버그 표시", key="bal_debug")
    with _bal_col2:
        _refresh_btn = st.button("잔고 새로고침", type="primary", use_container_width=True)

    if _refresh_btn:
        with st.spinner("잔고 조회 중..."):
            balance = api.get_balance()

        if "error" in balance:
            st.error(f"잔고 조회 실패: {balance['error']}")
            st.caption(f"TR_ID: {balance.get('tr_id', '?')} | 모드: {balance.get('mode', '?')} | 오류코드: {balance.get('msg_cd', '?')}")
            if balance.get('rt_cd') and balance.get('rt_cd') != '0':
                st.warning(
                    "💡 **잔고가 0원으로 나오거나 오류가 발생하는 주요 원인:**\n\n"
                    "1. **거래 모드 불일치** — 실제 계좌인데 '모의투자'로 연결했을 경우\n"
                    "   → API 연결 시 거래 모드를 **'실전투자'**로 변경하세요\n\n"
                    "2. **계좌번호 형식** — 계좌번호는 숫자만 입력 (하이픈 제외)\n"
                    "   → 예: `12345678` + `01` 형식 (총 10자리)\n\n"
                    "3. **App Key/Secret** — 실전투자용 키인지 확인\n"
                    "   → 모의투자 키로 실전 계좌 조회 불가"
                )
        else:
            _mode_badge = "🟢 실전투자" if balance.get("mode") == "실전" else "🟡 모의투자"
            st.caption(f"{_mode_badge} | TR_ID: {balance.get('tr_id', '?')} | 계좌: {balance.get('cano', '?')}**")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("총 평가금액", f"{balance.get('총평가금액', 0):,}원")
            col2.metric("총 매입금액", f"{balance.get('총매입금액', 0):,}원")
            col3.metric("총 평가손익", f"{balance.get('총평가손익', 0):,}원")
            col4.metric("예수금", f"{balance.get('예수금', 0):,}원")

            if all(balance.get(k, 0) == 0 for k in ["총평가금액", "예수금"]):
                st.warning(
                    "⚠️ 모든 금액이 0원입니다. 확인 사항:\n\n"
                    "- **거래 모드**: 현재 **" + balance.get('mode', '?') + "** 모드입니다. "
                    "실제 계좌라면 API 연결 시 **'실전투자'**를 선택하세요.\n"
                    "- **계좌번호**: 숫자만 입력했는지 확인 (하이픈 없이)\n"
                    "- **입금 반영**: 입금 후 익영업일 오전에 반영될 수 있습니다."
                )

            holdings = balance.get("holdings", [])
            if holdings:
                st.dataframe(pd.DataFrame(holdings), use_container_width=True)
            else:
                st.info("보유 종목이 없습니다.")

            if _show_debug:
                with st.expander("🔍 API 원본 응답 (output2)", expanded=True):
                    st.json(balance.get("_raw_output2", {}))

    st.markdown("---")

    st.subheader("수동 주문")
    st.caption(market_status_text())

    def _order_error_text(result: dict[str, object]) -> str:
        msg = str(result.get("error") or "주문 실패")
        msg_cd = str(result.get("msg_cd") or "").strip()
        tr_id = str(result.get("tr_id") or "").strip()
        mode = str(result.get("mode") or "").strip()
        if msg_cd in {"IGW00017", "INVALID_PDNO_LOCAL"}:
            msg = f"{msg} (국내주식 6자리 숫자 종목코드로 입력: 예 005930)"
        details = []
        if msg_cd:
            details.append(f"msg_cd={msg_cd}")
        if tr_id:
            details.append(f"tr_id={tr_id}")
        if mode:
            details.append(f"mode={mode}")
        return f"{msg} ({', '.join(details)})" if details else msg

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**매수 주문**")
        buy_ticker = st.text_input("매수 종목코드", key="buy_ticker", placeholder="005930")
        buy_qty = int(st.number_input("매수 수량", min_value=1, value=1, key="buy_qty"))
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
                    st.error(f"매수 실패: {_order_error_text(result)}")

    with col2:
        st.markdown("**매도 주문**")
        sell_ticker = st.text_input("매도 종목코드", key="sell_ticker", placeholder="005930")
        sell_qty = int(st.number_input("매도 수량", min_value=1, value=1, key="sell_qty"))
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
                    st.error(f"매도 실패: {_order_error_text(result)}")

    st.markdown("---")

    st.subheader("전략 기반 자동매매")

    trade_mode = st.radio("매매 모드", ["전략 기반", "적립식 매수 (DCA)"], horizontal=True, key="trade_mode")

    col1, col2 = st.columns(2)
    strategy_name = list(AVAILABLE_STRATEGIES.keys())[0]
    strategy_class = AVAILABLE_STRATEGIES[strategy_name]
    with col1:
        auto_ticker = st.text_input("감시 종목코드", value="005930", key="auto_ticker")
        if trade_mode == "전략 기반":
            strategy_name = str(st.selectbox("매매 전략", list(AVAILABLE_STRATEGIES.keys())) or strategy_name)
        auto_qty = int(st.number_input("1회 매매 수량", min_value=1, value=1, key="auto_qty"))

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
        interval_label = str(st.selectbox("실행 간격", list(interval_map.keys()), index=1, key="sched_interval") or "5분")
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
                    if result.get("status") != "success":
                        log_msg += f" | {_order_error_text(result)}"
                    st.session_state["trade_log"].append(log_msg)
                    if result.get("status") == "success":
                        add_trade(auto_ticker, "KR", "SELL", 0, auto_qty, f"스케줄러 {reason}")
                    st.session_state["auto_buy_avg"] = 0
                elif trade_mode == "적립식 매수 (DCA)":
                    result = api.buy_order(auto_ticker, auto_qty, 0)
                    log_msg = f"[{now_str}] DCA BUY: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                    if result.get("status") != "success":
                        log_msg += f" | {_order_error_text(result)}"
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
                        if result.get("status") != "success":
                            log_msg += f" | {_order_error_text(result)}"
                        st.session_state["trade_log"].append(log_msg)
                        if result.get("status") == "success":
                            add_trade(auto_ticker, "KR", "BUY", 0, auto_qty, f"스케줄러 매수 ({strategy.name})")
                            st.session_state["auto_buy_avg"] = current_price
                    elif signal == "SELL":
                        result = api.sell_order(auto_ticker, auto_qty, 0)
                        log_msg = f"[{now_str}] AUTO SELL: {auto_ticker} x {auto_qty} → {result.get('status', 'unknown')}"
                        if result.get("status") != "success":
                            log_msg += f" | {_order_error_text(result)}"
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

    _dashboard_jobs = get_autopilot_jobs(username)
    _dashboard_logs_raw = get_autopilot_logs(username)
    _dashboard_log_columns = ["username", "slot_idx", "log_type", "message", "created_at"]
    _dashboard_logs = _dashboard_logs_raw.copy() if isinstance(_dashboard_logs_raw, pd.DataFrame) else pd.DataFrame(columns=_dashboard_log_columns)

    _dashboard_log_rows = []
    if not _dashboard_logs.empty:
        for _col in _dashboard_log_columns:
            if _col not in _dashboard_logs.columns:
                _dashboard_logs[_col] = None
        for _row in _dashboard_logs.to_dict("records"):
            _created_at = pd.to_datetime(str(_row.get("created_at") or ""), errors="coerce")
            if pd.isna(_created_at):
                continue
            _dashboard_log_rows.append(
                {
                    "slot_idx": _row.get("slot_idx"),
                    "log_type": str(_row.get("log_type") or ""),
                    "message": str(_row.get("message") or ""),
                    "created_at": _created_at.to_pydatetime(),
                }
            )
        _dashboard_log_rows.sort(key=lambda _r: _r["created_at"], reverse=True)

    _today_date = datetime.now().date()
    _today_logs = [_row for _row in _dashboard_log_rows if _row["created_at"].date() == _today_date]

    _running_slots = sum(1 for _job in _dashboard_jobs if str(_job.get("status", "")).lower() == "running")

    _today_trade_count = 0
    _today_fail_count = 0
    if _today_logs:
        _today_trade_count = sum(
            1
            for _row in _today_logs
            if re.search(r"매수|매도|손절|익절|청산", _row["message"]) or re.search(r"trade", _row["log_type"], re.IGNORECASE)
        )
        _today_fail_count = sum(
            1
            for _row in _today_logs
            if re.search(r"실패|오류|error|fail", _row["message"], re.IGNORECASE)
            or re.search(r"error|fail", _row["log_type"], re.IGNORECASE)
        )

    _pnl_jobs = [j for j in _dashboard_jobs if str(j.get("status", "")).lower() == "running"]
    if not _pnl_jobs:
        _pnl_jobs = _dashboard_jobs
    _weighted_cap = 0.0
    _weighted_pnl_sum = 0.0
    for _job in _pnl_jobs:
        try:
            _cap = float(str(_job.get("capital", 0) or 0))
            _pnl = float(str(_job.get("daily_pnl", 0) or 0))
        except Exception:
            continue
        if _cap <= 0:
            continue
        _weighted_cap += _cap
        _weighted_pnl_sum += _cap * _pnl
    _daily_pnl = (_weighted_pnl_sum / _weighted_cap) if _weighted_cap > 0 else 0.0

    with st.expander("📊 오토파일럿 대시보드", expanded=True):
        _kpi1, _kpi2, _kpi3, _kpi4 = st.columns(4)
        _kpi1.metric("동작 중 슬롯 수", f"{_running_slots}개")
        _kpi2.metric("오늘 체결 건수", f"{_today_trade_count}건")
        _kpi3.metric("오늘 실패 건수", f"{_today_fail_count}건")
        _kpi4.metric("일간 손익(%)", f"{_daily_pnl:+.2f}%")

        _left_col, _right_col = st.columns(2)

        with _left_col:
            st.markdown("**최근 체결 5건**")
            if not _dashboard_log_rows:
                st.info("체결 로그가 없습니다.")
            else:
                _trade_logs = [
                    _row
                    for _row in _dashboard_log_rows
                    if re.search(r"매수|매도|손절|익절|청산", _row["message"])
                ][:5]
                if not _trade_logs:
                    st.info("체결 로그가 없습니다.")
                else:
                    _trade_rows = []
                    for _row in _trade_logs:
                        _msg = _row["message"]
                        _time_text = _row["created_at"].strftime("%H:%M:%S")
                        _symbol_match = re.search(r":\s*([^x@\[]+?)\s+x\d+", _msg)
                        _qty_match = re.search(r"x(\d+)", _msg)
                        if "매수" in _msg:
                            _side = "매수"
                        elif any(_kw in _msg for _kw in ["매도", "손절", "익절", "청산"]):
                            _side = "매도"
                        else:
                            _side = "-"
                        _trade_rows.append(
                            {
                                "시간": _time_text,
                                "종목": (_symbol_match.group(1).strip() if _symbol_match else "-"),
                                "매수/매도": _side,
                                "수량": int(_qty_match.group(1)) if _qty_match else 0,
                                "결과": "실패" if re.search(r"실패|오류|error|fail", _msg, re.IGNORECASE) else "성공",
                            }
                        )
                    st.dataframe(pd.DataFrame(_trade_rows), use_container_width=True, hide_index=True)

        with _right_col:
            st.markdown("**실패 사유 TOP 5**")
            if not _today_logs:
                st.info("오늘 실패 로그가 없습니다.")
            else:
                _fail_logs = [
                    _row
                    for _row in _today_logs
                    if re.search(r"error|fail", _row["log_type"], re.IGNORECASE)
                    or re.search(r"실패|오류|error|fail", _row["message"], re.IGNORECASE)
                ]
                if not _fail_logs:
                    st.info("오늘 실패 로그가 없습니다.")
                else:
                    _msg_cd_counter = Counter()
                    for _row in _fail_logs:
                        _msg_match = re.search(r"msg_cd\s*[:=]\s*([A-Z0-9_]+)", _row["message"])
                        _msg_cd_counter[_msg_match.group(1) if _msg_match else "UNKNOWN"] += 1
                    _top_fail = pd.DataFrame(
                        [{"msg_cd": _msg_cd, "건수": _cnt} for _msg_cd, _cnt in _msg_cd_counter.most_common(5)]
                    )
                    st.dataframe(_top_fail, use_container_width=True, hide_index=True)

    # ===================================================================
    if require_plan(user, "pro", "오토파일럿 모드"):
        # 오토파일럿 모드
        # ===================================================================
        st.subheader("🚀 오토파일럿 모드 (최대 5개 동시)")
        st.caption("AI가 종목 추천 → 자동 선택 → 포지션 사이징 → 매수/매도를 모두 자동 수행합니다.")
    
        _MAX_AP = 5
        _ap_ui_prefs = load_user_preferences(username, "autopilot_ui")
        if "ap_slot_count" not in st.session_state:
            try:
                _saved_slots = int(_ap_ui_prefs.get("slot_count", 1))
            except Exception:
                _saved_slots = 1
            st.session_state["ap_slot_count"] = max(1, min(_MAX_AP, _saved_slots))
    
        def _persist_ap_slots() -> None:
            save_user_preferences(
                username,
                "autopilot_ui",
                {"slot_count": int(st.session_state.get("ap_slot_count", 1))},
            )
    
        ap_add_col, ap_info_col = st.columns([1, 3])
        with ap_add_col:
            if st.button("➕ 슬롯 추가", use_container_width=True, key="ap_add_slot"):
                if st.session_state["ap_slot_count"] < _MAX_AP:
                    st.session_state["ap_slot_count"] += 1
                    _new_idx = st.session_state["ap_slot_count"] - 1
                    _np = f"ap{_new_idx}_"
                    st.session_state.setdefault(f"{_np}running", False)
                    st.session_state.setdefault(f"{_np}holdings", {})
                    st.session_state.setdefault(f"{_np}capital", 1_000_000)
                    st.session_state.setdefault(f"{_np}market", "KOSPI")
                    st.session_state.setdefault(f"{_np}mode", "일반 추천")
                    st.session_state.setdefault(f"{_np}max_stocks", 5)
                    st.session_state.setdefault(f"{_np}max_per", 20)
                    st.session_state.setdefault(f"{_np}sl", 5)
                    st.session_state.setdefault(f"{_np}tp", 15)
                    st.session_state.setdefault(f"{_np}daily_limit", 5)
                    st.session_state.setdefault(f"{_np}usdkrw", 1350.0)
                    _persist_ap_slots()
                    st.toast(f"AP-{_new_idx + 1} 슬롯이 추가되었습니다.")
                    st.rerun()
                else:
                    st.toast(f"최대 {_MAX_AP}개까지 가능합니다.")
        with ap_info_col:
            _running_count = sum(1 for i in range(st.session_state["ap_slot_count"]) if st.session_state.get(f"ap{i}_running", False))
            st.caption(f"슬롯: {st.session_state['ap_slot_count']}/{_MAX_AP} | 동작 중: {_running_count}개")
    
        _any_running = any(st.session_state.get(f"ap{i}_running", False) for i in range(st.session_state["ap_slot_count"]))
        if _any_running:
            _stop_col, _status_col = st.columns([1, 3])
            with _stop_col:
                if st.button("🛑 전체 오토파일럿 중지", type="primary", use_container_width=True, key="ap_stop_all"):
                    for _i in range(st.session_state["ap_slot_count"]):
                        st.session_state[f"ap{_i}_running"] = False
                        st.session_state[f"ap{_i}_holdings"] = {}
                    st.success("모든 오토파일럿이 중지되었습니다.")
                    st.rerun()
            with _status_col:
                _status_lines = []
                for _i in range(st.session_state["ap_slot_count"]):
                    if st.session_state.get(f"ap{_i}_running", False):
                        _h = st.session_state.get(f"ap{_i}_holdings", {})
                        _mkt = st.session_state.get(f"ap{_i}_market", "KOSPI")
                        _cap = int(st.session_state.get(f"ap{_i}_capital", 0))
                        _dpnl = float(st.session_state.get(f"ap{_i}_pnl", 0.0))
                        _status_lines.append(
                            f"AP-{_i+1} 🟢 | {_mkt} | 투자금 {_cap:,}원 | "
                            f"보유 {len(_h)}종목 | 손익 {_dpnl:+.2f}%"
                        )
                st.success("  ·  ".join(_status_lines) if _status_lines else "동작 중")
    
        _ap_tabs = st.tabs([f"AP-{i+1}" for i in range(st.session_state["ap_slot_count"])])
    
        for _slot_idx, _ap_tab in enumerate(_ap_tabs):
            _p = f"ap{_slot_idx}_"
            with _ap_tab:
                if f"{_p}running" not in st.session_state:
                    st.session_state[f"{_p}running"] = False
                if f"{_p}holdings" not in st.session_state:
                    st.session_state[f"{_p}holdings"] = {}
    
                with st.expander(f"AP-{_slot_idx+1} 설정", expanded=not st.session_state[f"{_p}running"]):
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        _capital = st.number_input("투자금 (원)", min_value=100_000, value=1_000_000, step=100_000, key=f"{_p}capital", format="%d")
                        _market = str(st.selectbox("시장", ["KOSPI", "KOSDAQ", "US"], key=f"{_p}market") or "KOSPI")
                        _mode = str(st.selectbox("추천 모드", ["일반 추천", "🔥 공격적 추천"], key=f"{_p}mode") or "일반 추천")
                    with _c2:
                        _max_stocks = st.slider("최대 보유 종목", 1, 10, 5, key=f"{_p}max_stocks")
                        _max_per = st.slider("종목당 비중 (%)", 10, 50, 20, key=f"{_p}max_per")
                        _sl = st.slider("손절 (%)", 1, 20, 5, key=f"{_p}sl")
                    _c3, _c4 = st.columns(2)
                    with _c3:
                        _tp = st.slider("익절 (%)", 5, 50, 15, key=f"{_p}tp")
                    with _c4:
                        _daily_limit = st.slider("일일 손실 한도 (%)", 1, 20, 5, key=f"{_p}daily_limit")
                    _usdkrw = float(st.session_state.get(f"{_p}usdkrw", 1350.0))
                    if _market == "US":
                        _usdkrw = float(
                            st.number_input(
                                "USD/KRW 환율 (시뮬레이션)",
                                min_value=900.0,
                                max_value=2000.0,
                                value=float(st.session_state.get(f"{_p}usdkrw", 1350.0)),
                                step=1.0,
                                key=f"{_p}usdkrw",
                            )
                        )
    
                    st.warning(
                        f"⚠️ 투자금 {_capital:,}원, 최대 {_max_stocks}종목, "
                        f"손절 -{_sl}%, 익절 +{_tp}%, 일일한도 -{_daily_limit}%"
                    )
                    if _market == "US":
                        st.info("US 시장은 현재 시뮬레이션 자동매매로 동작합니다. (추천/보유/손익 추적 지원)")
    
                _bg_running = ap_is_running(username, _slot_idx)
                _b1, _b2, _b3 = st.columns(3)
                with _b1:
                    if _bg_running:
                        if st.button("🛑 중지", type="primary", use_container_width=True, key=f"{_p}toggle"):
                            stop_background_autopilot(username, _slot_idx)
                            st.session_state[f"{_p}running"] = False
                            st.session_state[f"{_p}holdings"] = {}
                            st.success(f"AP-{_slot_idx+1} 중지됨")
                            st.rerun()
                    else:
                        if st.button("🚀 시작 (백그라운드)", type="primary", use_container_width=True, key=f"{_p}toggle"):
                            start_background_autopilot(
                                username=username,
                                slot_idx=_slot_idx,
                                market=_market,
                                mode=_mode,
                                capital=int(_capital),
                                max_stocks=int(_max_stocks),
                                max_per=int(_max_per),
                                stop_loss=float(_sl),
                                take_profit=float(_tp),
                                daily_limit=float(_daily_limit),
                                usdkrw=float(_usdkrw),
                            )
                            st.session_state[f"{_p}running"] = True
                            st.toast(f"🚀 AP-{_slot_idx+1} 백그라운드 실행 시작! 화면을 꺼도 계속 동작합니다.")
                            _notify_js = f"""
    <script>
    (function() {{
        if ('Notification' in window && Notification.permission === 'granted') {{
            new Notification('Archon AP-{_slot_idx+1} 시작', {{
                body: '{_market} | {_mode} | 투자금 {int(_capital):,}원',
                icon: '/favicon.ico'
            }});
        }} else if ('Notification' in window && Notification.permission !== 'denied') {{
            Notification.requestPermission().then(p => {{
                if (p === 'granted') {{
                    new Notification('Archon AP-{_slot_idx+1} 시작', {{
                        body: '{_market} | {_mode}',
                        icon: '/favicon.ico'
                    }});
                }}
            }});
        }}
    }})();
    </script>"""
                            st.markdown(_notify_js, unsafe_allow_html=True)
                            st.rerun()
                with _b3:
                    if st.button("🔔 알림 권한", use_container_width=True, key=f"{_p}notif"):
                        st.markdown("""
    <script>
    (function() {
        if ('Notification' in window) {
            Notification.requestPermission().then(p => {
                console.log('Notification permission:', p);
            });
        }
    })();
    </script>""", unsafe_allow_html=True)
                        st.toast("브라우저 알림 권한을 허용해주세요.")
                with _b2:
                    if st.button("📊 1회 스캔", use_container_width=True, key=f"{_p}scan"):
                        with st.spinner("AI 스캔 중..."):
                            try:
                                if _mode == "🔥 공격적 추천":
                                    if _market == "US":
                                        _sdf = _recommend_us_stocks(top_n=50, result_count=_max_stocks, aggressive=True)
                                    else:
                                        from analysis.recommender import recommend_aggressive_stocks
    
                                        _sdf = recommend_aggressive_stocks(market=_market, top_n=100, result_count=_max_stocks)
                                    _sc = "공격점수"
                                else:
                                    if _market == "US":
                                        _sdf = _recommend_us_stocks(top_n=40, result_count=_max_stocks, aggressive=False)
                                    else:
                                        from analysis.recommender import recommend_stocks
    
                                        _sdf = recommend_stocks(market=_market, top_n=50, result_count=_max_stocks)
                                    _sc = "종합점수"
                                if _sdf.empty:
                                    st.error("스캔 결과 없음")
                                else:
                                    st.success(f"{len(_sdf)}개 종목 발견")
                                    _capital_base = (float(_capital) / _usdkrw) if _market == "US" else float(_capital)
                                    _psc = int(_capital_base / len(_sdf))
                                    _plan = []
                                    for _, _r in _sdf.iterrows():
                                        _pr = float(_r["현재가"])
                                        if _market != "US":
                                            _pr = float(int(_pr))
                                        _score = float(_r[_sc]) if _sc in _r else 0.0
                                        _q = max(1, int(_psc // _pr)) if _pr > 0 else 0
                                        _price_text = f"{_pr:,.2f}" if _market == "US" else f"{int(_pr):,}"
                                        _sl_text = f"{(_pr * (1 - _sl / 100)):,.2f}" if _market == "US" else f"{int(_pr * (1 - _sl / 100)):,}"
                                        _tp_text = f"{(_pr * (1 + _tp / 100)):,.2f}" if _market == "US" else f"{int(_pr * (1 + _tp / 100)):,}"
                                        _plan.append({"종목명": str(_r["종목명"]), "현재가": _price_text, "점수": round(_score, 1), "수량": _q, "손절가": _sl_text, "익절가": _tp_text})
                                    st.dataframe(pd.DataFrame(_plan), use_container_width=True, hide_index=True)
                            except Exception as _e:
                                st.error(f"스캔 실패: {_e}")
    
                if _bg_running or st.session_state.get(f"{_p}running"):
                    import time as _apt
                    import json as _json_ap
                    _bg_job = next((j for j in get_autopilot_jobs(username) if int(str(j["slot_idx"])) == _slot_idx), None)
                    _bg_logs_raw = get_autopilot_logs(username, _slot_idx, limit=20)
                    if isinstance(_bg_logs_raw, list):
                        _bg_logs = _bg_logs_raw
                    else:
                        _bg_logs = []
                    if _bg_job:
                        _bg_holdings = _json_ap.loads(str(_bg_job.get("holdings") or "{}"))
                        _bg_pnl = float(str(_bg_job.get("daily_pnl") or 0.0))
                        _bg_runs = int(str(_bg_job.get("run_count") or 0))
                        _bg_next = str(_bg_job.get("next_run_at", "-") or "-")[:19]
                    else:
                        _bg_holdings = {}
                        _bg_pnl = 0.0
                        _bg_runs = 0
                        _bg_next = "-"
    
                    _notify_trade_js = ""
                    if _bg_logs:
                        _last_log = _bg_logs[-1] if _bg_logs else ""
                        if any(k in _last_log for k in ["매수", "손절", "익절", "청산"]):
                            _color_map = {"손절": "#EF4444", "익절": "#10B981", "청산": "#F59E0B", "매수": "#38BDF8"}
                            _ncolor = next((v for k, v in _color_map.items() if k in _last_log), "#94A3B8")
                            _notify_trade_js = f"""
    <script>
    (function() {{
        if ('Notification' in window && Notification.permission === 'granted') {{
            new Notification('Archon AP-{_slot_idx+1} 거래 알림', {{
                body: '{_last_log[:80]}',
                icon: '/favicon.ico'
            }});
        }}
    }})();
    </script>"""
    
                    _status_box = st.container()
                    if _notify_trade_js:
                        st.markdown(_notify_trade_js, unsafe_allow_html=True)
                    with _status_box:
                        st.markdown(f"""
                        <div style="border:1px solid #00D4AA44;border-left:4px solid #00D4AA;
                            background:rgba(0,212,170,0.07);border-radius:10px;
                            padding:0.85rem 1.1rem;margin-bottom:0.7rem;">
                            <span style="color:#00D4AA;font-weight:700;font-size:1rem;">
                                🚀 AP-{_slot_idx+1} 오토파일럿 실행 중
                            </span>
                            <span style="color:#94A3B8;font-size:0.85rem;margin-left:0.7rem;">
                                {datetime.now().strftime('%H:%M:%S')} 기준
                            </span>
                        </div>""", unsafe_allow_html=True)
    
                        _live_m1, _live_m2, _live_m3, _live_m4 = st.columns(4)
                        _cur_holdings = st.session_state.get(f"{_p}holdings", {})
                        _live_m1.metric("시장", _market)
                        _live_m2.metric("보유 종목", f"{len(_bg_holdings)}/{_max_stocks}")
                        _invested = sum(float(v["avg_price"]) * float(v["qty"]) for v in _bg_holdings.values())
                        _live_unit = " USD" if _market == "US" else " 원"
                        _live_m3.metric("투자된 금액", f"{_invested:,.2f}{_live_unit}" if _market == "US" else f"{int(_invested):,}{_live_unit}")
                        _live_m4.metric("일일 손익 / 실행 횟수", f"{_bg_pnl:+.2f}% / {_bg_runs}회")
    
                    if _bg_holdings:
                        with st.expander(f"📊 AP-{_slot_idx+1} 현재 보유 종목 ({len(_bg_holdings)}개)", expanded=True):
                            _hd_live = [
                                {
                                    "종목명": v["name"],
                                    "매수가": f"{float(v['avg_price']):,.2f}" if _market == "US" else f"{int(float(v['avg_price'])):,}",
                                    "수량": v["qty"],
                                }
                                for v in _bg_holdings.values()
                            ]
                            st.dataframe(pd.DataFrame(_hd_live), use_container_width=True, hide_index=True)
    
                    if _bg_logs:
                        with st.expander(f"📋 AP-{_slot_idx+1} 실행 로그 (최근 {len(_bg_logs)}건)", expanded=True):
                            if _bg_next != "-":
                                st.caption(f"다음 실행 예정: {_bg_next}")
                            for _log_line in reversed(_bg_logs[-15:]):
                                _color = "#EF4444" if any(k in _log_line for k in ["손절", "청산", "오류", "error"]) else \
                                         "#10B981" if "매수" in _log_line else \
                                         "#F59E0B" if "익절" in _log_line else "#94A3B8"
                                st.markdown(
                                    f"<div style='color:{_color};font-family:monospace;font-size:0.82rem;"
                                    f"padding:0.25rem 0;border-bottom:1px solid #1E293B;'>{_log_line}</div>",
                                    unsafe_allow_html=True,
                                )
    
                    if st.button(f"🛑 AP-{_slot_idx+1} 즉시 중지", key=f"{_p}stop_now", use_container_width=True):
                        stop_background_autopilot(username, _slot_idx)
                        st.session_state[f"{_p}running"] = False
                        st.session_state[f"{_p}holdings"] = {}
                        st.warning(f"AP-{_slot_idx+1} 즉시 중지됨")
                        st.rerun()
    
                    try:
                        if _mode == "🔥 공격적 추천":
                            if _market == "US":
                                _sdf = _recommend_us_stocks(top_n=50, result_count=_max_stocks, aggressive=True)
                            else:
                                from analysis.recommender import recommend_aggressive_stocks
    
                                _sdf = recommend_aggressive_stocks(market=_market, top_n=100, result_count=_max_stocks)
                            _sc = "공격점수"
                        else:
                            if _market == "US":
                                _sdf = _recommend_us_stocks(top_n=40, result_count=_max_stocks, aggressive=False)
                            else:
                                from analysis.recommender import recommend_stocks
    
                                _sdf = recommend_stocks(market=_market, top_n=50, result_count=_max_stocks)
                            _sc = "종합점수"
    
                        if not _sdf.empty:
                            _now = datetime.now().strftime("%H:%M:%S")
                            _h = st.session_state.get(f"{_p}holdings", {})
                            _market_code = "US" if _market == "US" else "KR"
                            _is_us_sim = _market == "US"
                            _capital_base = (float(_capital) / _usdkrw) if _is_us_sim else float(_capital)
                            _dpnl = 0.0
                            for _, _r in _sdf.iterrows():
                                _tk = str(_r["종목코드"])
                                _pr = float(_r["현재가"])
                                if not _is_us_sim:
                                    _pr = float(int(_pr))
                                _name = str(_r["종목명"])
                                if _tk in _h:
                                    _ent = _h[_tk]
                                    _pct = (_pr / _ent["avg_price"] - 1) * 100
                                    _dpnl += _pct * _ent["qty"] * _ent["avg_price"] / max(_capital_base, 1.0) * 100
                                    if _pct <= -_sl:
                                        _res = {"status": "success", "message": "US 시뮬레이션 매도"} if _is_us_sim else api.sell_order(_tk, _ent["qty"], 0)
                                        st.session_state["trade_log"].append(f"[{_now}] AP-{_slot_idx+1} 손절: {_name} {_pct:+.1f}%")
                                        if _res.get("status") == "success":
                                            _strategy_note = f"AP-{_slot_idx+1} 손절" + (" (US 시뮬레이션)" if _is_us_sim else "")
                                            add_trade(_tk, _market_code, "SELL", _pr, _ent["qty"], _strategy_note)
                                        del _h[_tk]
                                    elif _pct >= _tp:
                                        _res = {"status": "success", "message": "US 시뮬레이션 매도"} if _is_us_sim else api.sell_order(_tk, _ent["qty"], 0)
                                        st.session_state["trade_log"].append(f"[{_now}] AP-{_slot_idx+1} 익절: {_name} {_pct:+.1f}%")
                                        if _res.get("status") == "success":
                                            _strategy_note = f"AP-{_slot_idx+1} 익절" + (" (US 시뮬레이션)" if _is_us_sim else "")
                                            add_trade(_tk, _market_code, "SELL", _pr, _ent["qty"], _strategy_note)
                                        del _h[_tk]
                                else:
                                    if len(_h) < _max_stocks:
                                        _ps = _capital_base * (_max_per / 100)
                                        _q = max(1, int(_ps // _pr)) if _pr > 0 else 0
                                        if _q > 0:
                                            _res = {"status": "success", "message": "US 시뮬레이션 매수"} if _is_us_sim else api.buy_order(_tk, _q, 0)
                                            st.session_state["trade_log"].append(f"[{_now}] AP-{_slot_idx+1} 매수: {_name} x{_q}")
                                            if _res.get("status") == "success":
                                                _strategy_note = f"AP-{_slot_idx+1} 매수" + (" (US 시뮬레이션)" if _is_us_sim else "")
                                                add_trade(_tk, _market_code, "BUY", _pr, _q, _strategy_note)
                                                _h[_tk] = {"avg_price": _pr, "qty": _q, "name": _name}
                            st.session_state[f"{_p}holdings"] = _h
                            if _dpnl <= -_daily_limit:
                                st.session_state[f"{_p}running"] = False
                                st.error(f"⚠️ AP-{_slot_idx+1} 일일 손실 한도 도달. 자동 중지.")
                                _price_map = {str(row["종목코드"]): float(row["현재가"]) for _, row in _sdf.iterrows()}
                                for _t, _hh in list(_h.items()):
                                    _raw_exit = _price_map.get(_t, _hh["avg_price"])
                                    _exit_price = float(_raw_exit if _raw_exit is not None else _hh["avg_price"])
                                    _res = {"status": "success", "message": "US 시뮬레이션 강제청산"}
                                    if not _is_us_sim:
                                        _res = api.sell_order(_t, _hh["qty"], 0)
                                    st.session_state["trade_log"].append(
                                        f"[{_now}] AP-{_slot_idx+1} 강제청산: {_hh['name']} x{_hh['qty']}"
                                    )
                                    if _res.get("status") == "success":
                                        _strategy_note = f"AP-{_slot_idx+1} 강제청산" + (" (US 시뮬레이션)" if _is_us_sim else "")
                                        add_trade(_t, _market_code, "SELL", _exit_price, _hh["qty"], _strategy_note)
                                st.session_state[f"{_p}holdings"] = {}
                            if _h:
                                _hd = [{"종목명": v["name"], "매수가": f"{v['avg_price']:,.2f}" if _is_us_sim else f"{int(v['avg_price']):,}", "수량": v["qty"]} for v in _h.values()]
                                st.dataframe(pd.DataFrame(_hd), use_container_width=True, hide_index=True)
                    except Exception as _e:
                        st.error(f"AP-{_slot_idx+1} 오류: {_e}")
                    _apt.sleep(300)
                    st.rerun()
    
        st.markdown("---")
    
        st.subheader("🤖 AI 트레이딩 어시스턴트")
        st.caption("자연어로 오토파일럿을 제어하세요. 예: '손절을 3%로 바꿔줘', '종목 수를 3개로 줄여', '공격적 모드로 전환'")
    
        if "ap_chat_messages" not in st.session_state:
            st.session_state["ap_chat_messages"] = []
        if "ap_openai_key" not in st.session_state:
            from data.database import load_user_setting
            st.session_state["ap_openai_key"] = load_user_setting(username, "openai_api_key", "")
    
        ap_api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state["ap_openai_key"], key="ap_ai_key")
        if ap_api_key and ap_api_key != st.session_state["ap_openai_key"]:
            st.session_state["ap_openai_key"] = ap_api_key
            from data.database import save_user_setting
            save_user_setting(username, "openai_api_key", ap_api_key)
    
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
    
                ap_capital = int(st.session_state.get("ap_capital", 1_000_000))
                ap_market = str(st.session_state.get("ap_market", "KOSPI"))
                ap_mode = str(st.session_state.get("ap_mode", "일반 추천"))
                ap_max_stocks = int(st.session_state.get("ap_max_stocks", 5))
                ap_max_per_stock = int(st.session_state.get("ap_max_per_stock", 20))
                ap_stop_loss = int(st.session_state.get("ap_stop_loss", 5))
                ap_take_profit = int(st.session_state.get("ap_take_profit", 15))
                ap_daily_loss_limit = int(st.session_state.get("ap_daily_limit", 5))
    
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
                    import json as _json
                    OpenAI = importlib.import_module("openai").OpenAI
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

    show_legal_disclaimer()

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

    show_legal_disclaimer()
