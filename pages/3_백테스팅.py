"""
백테스팅 페이지
- 투자 전략 과거 성과 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import plotly.graph_objects as go
from data.fetcher import fetch_stock
from analysis.backtest import (
    BacktestEngine, STRATEGIES,
    golden_cross_strategy, rsi_strategy, macd_strategy, bollinger_strategy
)
from config.styles import inject_pro_css
from config.auth import require_pro

st.set_page_config(page_title="백테스팅", page_icon="🔬", layout="wide")
require_pro()
inject_pro_css()
st.title("🔬 백테스팅 시스템")
st.markdown("과거 데이터를 기반으로 투자 전략의 성과를 테스트합니다.")

# === 사이드바 설정 ===
st.sidebar.header("백테스팅 설정")
market = st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"])
market_code = market.split(" ")[0]

if market_code == "US":
    ticker = st.sidebar.text_input("종목 티커", value="AAPL")
else:
    ticker = st.sidebar.text_input("종목 코드", value="005930")

period = st.sidebar.selectbox("테스트 기간", ["6mo", "1y", "2y", "5y"], index=1)

st.sidebar.markdown("---")
st.sidebar.header("투자 설정")
initial_capital = st.sidebar.number_input(
    "초기 자본금 (원)", value=10_000_000,
    min_value=100_000, step=1_000_000, format="%d"
)
commission = st.sidebar.number_input(
    "수수료율 (%)", value=0.015, min_value=0.0, max_value=1.0,
    step=0.005, format="%.3f"
)

st.sidebar.markdown("---")
st.sidebar.header("전략 선택")
strategy_name = st.sidebar.selectbox("투자 전략", list(STRATEGIES.keys()))

# 전략별 파라미터
st.sidebar.markdown("---")
st.sidebar.header("전략 파라미터")

if strategy_name == "골든크로스/데드크로스":
    short_ma = st.sidebar.slider("단기 이동평균", 3, 30, 5)
    long_ma = st.sidebar.slider("장기 이동평균", 10, 200, 20)
elif strategy_name == "RSI 전략":
    rsi_buy = st.sidebar.slider("매수 기준 (RSI 이하)", 10, 50, 30)
    rsi_sell = st.sidebar.slider("매도 기준 (RSI 이상)", 50, 90, 70)
elif strategy_name == "MACD 전략":
    st.sidebar.info("MACD(12,26,9) 기본 설정 사용")
elif strategy_name == "볼린저밴드 전략":
    bb_period = st.sidebar.slider("볼린저 기간", 10, 50, 20)
    bb_std = st.sidebar.slider("표준편차 배수", 1.0, 3.0, 2.0, 0.5)

# === 백테스팅 실행 ===
if st.sidebar.button("백테스팅 실행", type="primary", use_container_width=True):
    with st.spinner(f"{ticker} 백테스팅 실행 중..."):
        df = fetch_stock(ticker, market_code, period)

        if df.empty:
            st.error("데이터를 가져올 수 없습니다.")
        else:
            # 전략 시그널 생성
            if strategy_name == "골든크로스/데드크로스":
                signals = golden_cross_strategy(df, short_ma, long_ma)
            elif strategy_name == "RSI 전략":
                signals = rsi_strategy(df, rsi_buy, rsi_sell)
            elif strategy_name == "MACD 전략":
                signals = macd_strategy(df)
            elif strategy_name == "볼린저밴드 전략":
                signals = bollinger_strategy(df, bb_period, bb_std)

            # 백테스팅 실행
            engine = BacktestEngine(df, initial_capital, commission / 100)
            results = engine.run(signals)
            equity = engine.get_equity_curve()
            trades = engine.get_trades()

            # === 결과 표시 ===
            st.subheader("백테스팅 결과")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("총 수익률", f"{results.get('총 수익률 (%)', 0):.2f}%")
            col2.metric("연환산 수익률", f"{results.get('연환산 수익률 (%)', 0):.2f}%")
            col3.metric("최대 낙폭 (MDD)", f"{results.get('최대 낙폭 MDD (%)', 0):.2f}%")
            col4.metric("샤프 비율", f"{results.get('샤프 비율', 0):.2f}")

            col5, col6, col7, col8 = st.columns(4)
            col5.metric("총 거래 횟수", results.get("총 거래 횟수", 0))
            col6.metric("승률", f"{results.get('승률 (%)', 0):.1f}%")
            col7.metric("최종 자산", f"{results.get('최종 자산', 0):,.0f}")
            col8.metric("초기 자본", f"{initial_capital:,.0f}")

            st.markdown("---")

            # 자산 추이 차트
            st.subheader("자산 추이")
            if not equity.empty:
                fig = go.Figure()

                # 전략 수익 곡선
                fig.add_trace(go.Scatter(
                    x=equity.index, y=equity["equity"],
                    name="전략 자산", line=dict(color="blue", width=2)
                ))

                # 벤치마크 (단순 보유)
                buy_hold = initial_capital * (df["Close"] / df["Close"].iloc[0])
                fig.add_trace(go.Scatter(
                    x=df.index, y=buy_hold,
                    name="단순 보유 (Buy & Hold)",
                    line=dict(color="gray", width=1, dash="dash")
                ))

                # 매수/매도 포인트
                if not trades.empty:
                    buy_trades = trades[trades["action"] == "BUY"]
                    sell_trades = trades[trades["action"] == "SELL"]

                    if not buy_trades.empty:
                        buy_equity = [equity.loc[d, "equity"] if d in equity.index else None for d in buy_trades["date"]]
                        fig.add_trace(go.Scatter(
                            x=buy_trades["date"], y=buy_equity,
                            mode="markers", name="매수",
                            marker=dict(symbol="triangle-up", size=12, color="red")
                        ))

                    if not sell_trades.empty:
                        sell_equity = [equity.loc[d, "equity"] if d in equity.index else None for d in sell_trades["date"]]
                        fig.add_trace(go.Scatter(
                            x=sell_trades["date"], y=sell_equity,
                            mode="markers", name="매도",
                            marker=dict(symbol="triangle-down", size=12, color="blue")
                        ))

                fig.update_layout(
                    height=500, xaxis_title="날짜", yaxis_title="자산 (원)",
                    hovermode="x unified", template="plotly_dark",
                )
                st.plotly_chart(fig, use_container_width=True)

            # 거래 내역
            if not trades.empty:
                st.subheader("거래 내역")
                display_trades = trades.copy()
                display_trades["date"] = display_trades["date"].astype(str)
                st.dataframe(display_trades, use_container_width=True)
            else:
                st.info("해당 기간에 매매 시그널이 발생하지 않았습니다.")

# === 전략 비교 ===
st.markdown("---")
st.subheader("전략 비교")
if st.button("모든 전략 비교 실행", use_container_width=True):
    compare_ticker = ticker if "ta_ticker" not in st.session_state else ticker
    with st.spinner("모든 전략 비교 중..."):
        df = fetch_stock(ticker, market_code, period)
        if df.empty:
            st.error("데이터를 가져올 수 없습니다.")
        else:
            fig_compare = go.Figure()
            results_table = []

            for name, strategy_func in STRATEGIES.items():
                signals = strategy_func(df)
                engine = BacktestEngine(df, initial_capital, commission / 100)
                res = engine.run(signals)
                eq = engine.get_equity_curve()

                if not eq.empty:
                    fig_compare.add_trace(go.Scatter(
                        x=eq.index, y=eq["equity"], name=name, mode="lines"
                    ))

                results_table.append({
                    "전략": name,
                    "총 수익률 (%)": res.get("총 수익률 (%)", 0),
                    "MDD (%)": res.get("최대 낙폭 MDD (%)", 0),
                    "샤프 비율": res.get("샤프 비율", 0),
                    "승률 (%)": res.get("승률 (%)", 0),
                    "거래 횟수": res.get("총 거래 횟수", 0),
                })

            # Buy & Hold 추가
            buy_hold = initial_capital * (df["Close"] / df["Close"].iloc[0])
            fig_compare.add_trace(go.Scatter(
                x=df.index, y=buy_hold,
                name="Buy & Hold", line=dict(dash="dash", color="black")
            ))

            fig_compare.update_layout(
                title="전략별 자산 추이 비교",
                height=500, xaxis_title="날짜", yaxis_title="자산 (원)",
                hovermode="x unified", template="plotly_dark",
            )
            st.plotly_chart(fig_compare, use_container_width=True)

            import pandas as pd
            st.dataframe(pd.DataFrame(results_table), use_container_width=True)
