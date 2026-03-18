from typing import Any, cast

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis.backtest import (
    STRATEGIES,
    BacktestEngine,
    aggressive_momentum_strategy,
    bollinger_strategy,
    golden_cross_strategy,
    macd_strategy,
    optimize_strategy_params,
    rsi_strategy,
    volatility_breakout_strategy,
)
from config.auth import is_paid, is_pro
from config.styles import require_plan, show_legal_disclaimer
from data.fetcher import fetch_stock
from views.analysis._tools_helper import (
    render_news_tab,
    render_risk_tab,
    render_strategy_comparison,
    render_strategy_optimizer,
)


def render_tools(user: dict[str, Any]) -> None:
    tab_backtest, tab_risk, tab_news = st.tabs(["백테스팅", "리스크분석", "뉴스감성분석"])

    with tab_backtest:
        st.header("🔬 백테스팅 시스템")
        st.markdown("과거 데이터를 기반으로 투자 전략의 성과를 테스트합니다.")

        if not require_plan(user, "plus", "백테스팅"):
            show_legal_disclaimer()
        else:
            st.sidebar.header("백테스팅 설정")
            market = st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"], key="bt_market") or "US (미국)"
            market_code = market.split(" ")[0]

            if market_code == "US":
                ticker = st.sidebar.text_input("종목 티커", value="AAPL", key="bt_ticker_us")
            else:
                ticker = st.sidebar.text_input("종목 코드", value="005930", key="bt_ticker_kr")

            period = st.sidebar.selectbox("테스트 기간", ["6mo", "1y", "2y", "5y"], index=1, key="bt_period") or "1y"

            st.sidebar.markdown("---")
            st.sidebar.header("투자 설정")
            initial_capital = st.sidebar.number_input(
                "초기 자본금 (원)",
                value=10_000_000,
                min_value=100_000,
                step=1_000_000,
                format="%d",
                key="bt_initial_capital",
            )
            commission = st.sidebar.number_input(
                "수수료율 (%)",
                value=0.015,
                min_value=0.0,
                max_value=1.0,
                step=0.005,
                format="%.3f",
                key="bt_commission",
            )

            st.sidebar.markdown("---")
            st.sidebar.header("전략 선택")
            strategy_name = st.sidebar.selectbox("투자 전략", list(STRATEGIES.keys()), key="bt_strategy_name") or list(STRATEGIES.keys())[0]

            st.sidebar.markdown("---")
            st.sidebar.header("전략 파라미터")

            short_ma, long_ma = 5, 20
            rsi_buy, rsi_sell = 30, 70
            bb_period, bb_std = 20, 2.0
            vb_k, vol_mult = 0.5, 2.0

            if strategy_name == "골든크로스/데드크로스":
                short_ma = st.sidebar.slider("단기 이동평균", 3, 30, 5, key="bt_short_ma")
                long_ma = st.sidebar.slider("장기 이동평균", 10, 200, 20, key="bt_long_ma")
            elif strategy_name == "RSI 전략":
                rsi_buy = st.sidebar.slider("매수 기준 (RSI 이하)", 10, 50, 30, key="bt_rsi_buy")
                rsi_sell = st.sidebar.slider("매도 기준 (RSI 이상)", 50, 90, 70, key="bt_rsi_sell")
            elif strategy_name == "MACD 전략":
                st.sidebar.info("MACD(12,26,9) 기본 설정 사용")
            elif strategy_name == "볼린저밴드 전략":
                bb_period = st.sidebar.slider("볼린저 기간", 10, 50, 20, key="bt_bb_period")
                bb_std = st.sidebar.slider("표준편차 배수", 1.0, 3.0, 2.0, 0.5, key="bt_bb_std")
            elif strategy_name == "변동성 돌파 전략":
                vb_k = st.sidebar.slider("돌파 계수 (k)", 0.1, 1.0, 0.5, 0.1, key="bt_vb_k")
            elif strategy_name == "공격적 모멘텀 전략":
                rsi_buy = st.sidebar.slider("매수 RSI 상향돌파 기준", 20, 60, 40, key="bt_mom_rsi_buy")
                rsi_sell = st.sidebar.slider("매도 RSI 상향돌파 기준", 60, 90, 75, key="bt_mom_rsi_sell")
                vol_mult = st.sidebar.slider("거래량 배수", 1.0, 5.0, 2.0, 0.1, key="bt_vol_mult")

            if st.sidebar.button("백테스팅 실행", type="primary", use_container_width=True, key="bt_run"):
                with st.spinner(f"{ticker} 백테스팅 실행 중..."):
                    df = fetch_stock(ticker, market_code, period)

                    if df.empty:
                        st.error("데이터를 가져올 수 없습니다.")
                    else:
                        st.session_state["last_backtest_df"] = df.copy()
                        st.session_state["last_backtest_strategy"] = strategy_name

                        if strategy_name == "골든크로스/데드크로스":
                            signals = golden_cross_strategy(df, short_ma, long_ma)
                        elif strategy_name == "RSI 전략":
                            signals = rsi_strategy(df, rsi_buy, rsi_sell)
                        elif strategy_name == "MACD 전략":
                            signals = macd_strategy(df)
                        elif strategy_name == "볼린저밴드 전략":
                            signals = bollinger_strategy(df, bb_period, bb_std)
                        elif strategy_name == "변동성 돌파 전략":
                            signals = volatility_breakout_strategy(df, vb_k)
                        elif strategy_name == "공격적 모멘텀 전략":
                            signals = aggressive_momentum_strategy(df, rsi_buy, rsi_sell, vol_mult)
                        else:
                            signals = STRATEGIES[strategy_name](df)

                        engine = BacktestEngine(df, initial_capital, commission / 100)
                        results = engine.run(signals)
                        equity = engine.get_equity_curve()
                        trades = engine.get_trades()

                        st.subheader("백테스팅 결과")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("총 수익률", f"{results.get('총 수익률 (%)', 0):.2f}%")
                        col2.metric("연환산 수익률", f"{results.get('연환산 수익률 (%)', 0):.2f}%")
                        col3.metric("최대 낙폭 (MDD)", f"{results.get('최대 낙폭 MDD (%)', 0):.2f}%")
                        col4.metric("샤프 비율", f"{results.get('샤프 비율', 0):.2f}")

                        col5, col6, col7, col8 = st.columns(4)
                        col5.metric("소르티노 비율", f"{results.get('소르티노 비율', 0):.2f}")
                        col6.metric("칼마 비율", f"{results.get('칼마 비율', 0):.2f}")
                        col7.metric("손익비", f"{results.get('손익비 (Profit Factor)', 0):.2f}")
                        col8.metric("승률", f"{results.get('승률 (%)', 0):.1f}%")

                        col9, col10, col11, col12 = st.columns(4)
                        col9.metric("총 거래 횟수", results.get("총 거래 횟수", 0))
                        col10.metric("평균 수익", f"{results.get('평균 수익', 0):,.0f}")
                        col11.metric("평균 손실", f"{results.get('평균 손실', 0):,.0f}")
                        col12.metric("최종 자산", f"{results.get('최종 자산', 0):,.0f}")

                        st.markdown("---")

                        st.subheader("자산 추이")
                        if not equity.empty:
                            fig = go.Figure()

                            fig.add_trace(go.Scatter(x=equity.index, y=equity["equity"], name="전략 자산", line=dict(color="blue", width=2)))

                            buy_hold = initial_capital * (df["Close"] / df["Close"].iloc[0])
                            fig.add_trace(
                                go.Scatter(
                                    x=df.index,
                                    y=buy_hold,
                                    name="단순 보유 (Buy & Hold)",
                                    line=dict(color="gray", width=1, dash="dash"),
                                )
                            )

                            if not trades.empty:
                                buy_trades = trades[trades["action"] == "BUY"]
                                sell_trades = trades[trades["action"] == "SELL"]

                                if not buy_trades.empty:
                                    buy_equity = [equity.loc[d, "equity"] if d in equity.index else None for d in buy_trades["date"]]
                                    fig.add_trace(
                                        go.Scatter(
                                            x=buy_trades["date"],
                                            y=buy_equity,
                                            mode="markers",
                                            name="매수",
                                            marker=dict(symbol="triangle-up", size=12, color="red"),
                                        )
                                    )

                                if not sell_trades.empty:
                                    sell_equity = [equity.loc[d, "equity"] if d in equity.index else None for d in sell_trades["date"]]
                                    fig.add_trace(
                                        go.Scatter(
                                            x=sell_trades["date"],
                                            y=sell_equity,
                                            mode="markers",
                                            name="매도",
                                            marker=dict(symbol="triangle-down", size=12, color="blue"),
                                        )
                                    )

                            fig.update_layout(
                                height=500,
                                xaxis_title="날짜",
                                yaxis_title="자산 (원)",
                                hovermode="x unified",
                                template="plotly_dark",
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        if not trades.empty:
                            st.subheader("거래 내역")
                            display_trades = trades.copy()
                            display_trades["date"] = display_trades["date"].astype(str)
                            st.dataframe(display_trades, use_container_width=True)
                        else:
                            st.info("해당 기간에 매매 시그널이 발생하지 않았습니다.")

            render_strategy_optimizer(initial_capital)
            render_strategy_comparison(ticker, market_code, period, initial_capital, commission)

            show_legal_disclaimer()

    with tab_risk:
        render_risk_tab(user)

    with tab_news:
        render_news_tab(user)
