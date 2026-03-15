import os
import sys
import time
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.auth import is_pro, require_auth
from config.styles import inject_pro_css, show_legal_disclaimer
from data.database import add_trade, get_trades
from data.fetcher import FX_PAIRS, fetch_fx_pair, get_fx_spot_rate

st.set_page_config(page_title="외환 자동매매", page_icon="💱", layout="wide")
user = require_auth()
inject_pro_css()

if not is_pro(user):
    st.warning("외환 자동매매는 Pro 플랜 전용입니다.")
    st.stop()

st.title("💱 외환 자동매매 (FX Autopilot)")
st.caption("주요 통화쌍의 기술적 지표 기반 시뮬레이션 자동매매 | 실제 브로커 API 연결 시 실거래 가능")

PAIR_LIST = list(FX_PAIRS.keys())

AP_DEFAULTS = {
    "fx_pair": "USD/KRW",
    "fx_capital": 10_000_000,
    "fx_lot_size": 1000,
    "fx_sl_pct": 1.0,
    "fx_tp_pct": 2.0,
    "fx_strategy": "MA 크로스",
    "fx_running": False,
    "fx_position": None,
    "fx_trade_log": [],
    "fx_pnl": 0.0,
}
for k, v in AP_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

tab1, tab2, tab3 = st.tabs(["📊 시장 현황", "⚡ 자동매매", "📋 거래 로그"])

with tab1:
    st.subheader("주요 통화쌍 현재 환율")
    rate_cols = st.columns(4)
    for idx, pair in enumerate(PAIR_LIST):
        rate = get_fx_spot_rate(pair)
        rate_cols[idx % 4].metric(pair, f"{rate:,.4f}" if rate else "로딩중...")

    st.markdown("---")
    selected_pair = st.selectbox("차트 조회", PAIR_LIST, key="chart_pair")
    period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], index=2)

    if st.button("차트 불러오기", use_container_width=True):
        with st.spinner("데이터 로딩 중..."):
            df = fetch_fx_pair(selected_pair, period=period)
        if df.empty:
            st.error("데이터를 가져올 수 없습니다.")
        else:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name=selected_pair
            ))
            ma20 = df["Close"].rolling(20).mean()
            ma60 = df["Close"].rolling(60).mean()
            fig.add_trace(go.Scatter(x=df.index, y=ma20, name="MA20", line=dict(color="#38BDF8", width=1)))
            fig.add_trace(go.Scatter(x=df.index, y=ma60, name="MA60", line=dict(color="#F97316", width=1)))
            fig.update_layout(
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font_color="#E2E8F0", height=420, xaxis_rangeslider_visible=False,
                title=f"{selected_pair} 캔들차트"
            )
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("FX 오토파일럿 설정")
    col1, col2 = st.columns(2)
    with col1:
        fx_pair = str(st.selectbox("통화쌍", PAIR_LIST,
            index=PAIR_LIST.index(st.session_state["fx_pair"])
            if st.session_state["fx_pair"] in PAIR_LIST else 0) or PAIR_LIST[0])
        fx_capital = int(st.number_input("투자금 (원)", min_value=100_000, value=int(st.session_state["fx_capital"]), step=100_000))
        fx_lot = int(st.number_input("1회 매매 단위", min_value=100, value=int(st.session_state["fx_lot_size"]), step=100))
        fx_strategy = str(st.selectbox("전략", ["MA 크로스", "RSI 역추세", "볼린저 밴드 돌파"]) or "MA 크로스")
    with col2:
        fx_sl = float(st.slider("손절 (%)", 0.5, 5.0, float(st.session_state["fx_sl_pct"]), 0.1))
        fx_tp = float(st.slider("익절 (%)", 0.5, 10.0, float(st.session_state["fx_tp_pct"]), 0.1))
        st.info(
            f"통화쌍: {fx_pair}\n\n"
            f"투자금: {fx_capital:,}원 | 단위: {fx_lot:,}\n\n"
            f"손절 -{fx_sl}% / 익절 +{fx_tp}%"
        )

    if st.session_state["fx_running"]:
        if st.button("⏹️ 오토파일럿 중지", type="primary", use_container_width=True):
            st.session_state["fx_running"] = False
            st.session_state["fx_position"] = None
            st.rerun()
    else:
        if st.button("▶️ 오토파일럿 시작", type="primary", use_container_width=True):
            st.session_state.update({
                "fx_pair": fx_pair, "fx_capital": fx_capital,
                "fx_lot_size": fx_lot, "fx_sl_pct": fx_sl,
                "fx_tp_pct": fx_tp, "fx_strategy": fx_strategy,
                "fx_running": True, "fx_pnl": 0.0,
            })
            st.rerun()

    if st.session_state["fx_running"]:
        st.success(f"🟢 오토파일럿 실행 중 | {st.session_state['fx_pair']} | {st.session_state['fx_strategy']}")
        run_placeholder = st.empty()

        with st.spinner("환율 및 지표 계산 중..."):
            df_ap = fetch_fx_pair(st.session_state["fx_pair"], period="6mo")

        if df_ap.empty or len(df_ap) < 30:
            st.error("데이터 부족으로 분석 불가")
            st.session_state["fx_running"] = False
        else:
            close = df_ap["Close"]
            now_str = datetime.now().strftime("%H:%M:%S")
            current_rate = float(close.iloc[-1])

            strategy = st.session_state["fx_strategy"]
            signal = "HOLD"

            if strategy == "MA 크로스":
                ma5 = float(close.rolling(5).mean().iloc[-1])
                ma20 = float(close.rolling(20).mean().iloc[-1])
                ma5_prev = float(close.rolling(5).mean().iloc[-2])
                ma20_prev = float(close.rolling(20).mean().iloc[-2])
                if ma5_prev <= ma20_prev and ma5 > ma20:
                    signal = "BUY"
                elif ma5_prev >= ma20_prev and ma5 < ma20:
                    signal = "SELL"

            elif strategy == "RSI 역추세":
                delta = close.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, 1e-10)
                rsi = float((100 - 100 / (1 + rs)).iloc[-1])
                if rsi < 30:
                    signal = "BUY"
                elif rsi > 70:
                    signal = "SELL"

            elif strategy == "볼린저 밴드 돌파":
                ma20b = close.rolling(20).mean()
                std20 = close.rolling(20).std()
                upper = float((ma20b + 2 * std20).iloc[-1])
                lower = float((ma20b - 2 * std20).iloc[-1])
                if current_rate < lower:
                    signal = "BUY"
                elif current_rate > upper:
                    signal = "SELL"

            pos = st.session_state.get("fx_position")
            lot = int(st.session_state["fx_lot_size"])
            sl_pct = float(st.session_state["fx_sl_pct"])
            tp_pct = float(st.session_state["fx_tp_pct"])

            if pos is not None:
                entry = float(pos["entry_rate"])
                pct = (current_rate / entry - 1) * 100
                if pos["direction"] == "SELL":
                    pct = -pct
                st.session_state["fx_pnl"] = pct

                if pct <= -sl_pct:
                    st.session_state["fx_trade_log"].append(
                        f"[{now_str}] 손절 클로즈 {st.session_state['fx_pair']} "
                        f"({pos['direction']}) {pct:+.2f}%"
                    )
                    add_trade(st.session_state["fx_pair"].replace("/", ""), "FX", "SELL", current_rate, lot, "FX 손절")
                    st.session_state["fx_position"] = None
                elif pct >= tp_pct:
                    st.session_state["fx_trade_log"].append(
                        f"[{now_str}] 익절 클로즈 {st.session_state['fx_pair']} "
                        f"({pos['direction']}) {pct:+.2f}%"
                    )
                    add_trade(st.session_state["fx_pair"].replace("/", ""), "FX", "SELL", current_rate, lot, "FX 익절")
                    st.session_state["fx_position"] = None
            else:
                if signal in ("BUY", "SELL"):
                    st.session_state["fx_position"] = {
                        "direction": signal, "entry_rate": current_rate,
                        "lot": lot, "pair": st.session_state["fx_pair"],
                    }
                    st.session_state["fx_trade_log"].append(
                        f"[{now_str}] {signal} {st.session_state['fx_pair']} @ {current_rate:.4f}"
                    )
                    action = "BUY" if signal == "BUY" else "SELL"
                    add_trade(st.session_state["fx_pair"].replace("/", ""), "FX", action, current_rate, lot, f"FX {strategy}")

            with run_placeholder.container():
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("현재 환율", f"{current_rate:.4f}")
                mc2.metric("시그널", signal)
                pos_info = f"{pos['direction']} @ {float(pos['entry_rate']):.4f}" if pos else "없음"
                mc3.metric("포지션", pos_info)
                mc4.metric("평가손익", f"{float(st.session_state['fx_pnl']):+.2f}%")

            if st.session_state["fx_trade_log"]:
                st.text_area("실행 로그", "\n".join(st.session_state["fx_trade_log"][-20:]), height=140)

with tab3:
    st.subheader("FX 거래 내역")
    trades = get_trades(limit=200)
    if not trades.empty and "market" in trades.columns:
        fx_trades = trades[trades["market"] == "FX"]
        if fx_trades.empty:
            st.info("FX 거래 내역이 없습니다.")
        else:
            st.dataframe(fx_trades, use_container_width=True, hide_index=True)
    else:
        st.info("거래 내역이 없습니다.")

show_legal_disclaimer()
