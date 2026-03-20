from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.auth import is_pro
from config.styles import show_legal_disclaimer
from data.fetcher import fetch_stock


def render_risk_tab(user: dict[str, Any]) -> None:
    """Render the risk analysis tab."""
    st.header("Risk Analysis & Monte Carlo")
    fetch_stock_fn = fetch_stock

    if not is_pro(user):
        st.warning("💎 Pro 전용 기능입니다.")
        show_legal_disclaimer()
        return

    rtab1, rtab2, rtab3, rtab4 = st.tabs(
        ["Risk Metrics", "Monte Carlo Simulation", "Efficient Frontier", "Leverage Simulator"]
    )

    with rtab1:
        st.sidebar.header("Risk Settings")
        market = st.sidebar.selectbox("Market", ["KR", "US"], key="risk_market")
        ticker = st.sidebar.text_input("Ticker", value="005930" if market == "KR" else "AAPL", key="risk_ticker")
        benchmark = st.sidebar.text_input("Benchmark", value="069500" if market == "KR" else "SPY", key="benchmark")
        period = st.sidebar.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="risk_period")

        if st.sidebar.button("Analyze Risk", type="primary", key="btn_risk"):
            with st.spinner("Calculating risk metrics..."):
                df = fetch_stock_fn(ticker, market, period)
                df_bench = fetch_stock_fn(benchmark, market, period)

            if df.empty:
                st.error("Failed to fetch data.")
            else:
                from analysis.risk import calc_beta_alpha, calc_risk_metrics

                returns = cast(pd.Series, df["Close"].pct_change().dropna())
                metrics = calc_risk_metrics(returns)

                st.subheader("Risk Dashboard")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Annual Return", f"{metrics.get('연간 수익률 (%)', 0):.2f}%")
                c2.metric("Annual Volatility", f"{metrics.get('연간 변동성 (%)', 0):.2f}%")
                c3.metric("Sharpe Ratio", f"{metrics.get('샤프 비율', 0):.3f}")
                c4.metric("Sortino Ratio", f"{metrics.get('소르티노 비율', 0):.3f}")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("VaR 95%", f"{metrics.get('VaR 95% (%)', 0):.3f}%")
                c6.metric("CVaR 95%", f"{metrics.get('CVaR 95% (%)', 0):.3f}%")
                c7.metric("Best Day", f"{metrics.get('최대 일일 이익 (%)', 0):.2f}%")
                c8.metric("Worst Day", f"{metrics.get('최대 일일 손실 (%)', 0):.2f}%")

                if not df_bench.empty:
                    bench_returns = cast(pd.Series, df_bench["Close"].pct_change().dropna())
                    beta_alpha = calc_beta_alpha(returns, bench_returns)
                    c9, c10, c11, c12 = st.columns(4)
                    c9.metric("Beta", f"{beta_alpha['beta']:.3f}")
                    c10.metric("Alpha (%)", f"{beta_alpha['alpha']:.3f}")
                    c11.metric("R-Squared", f"{beta_alpha['r_squared']:.3f}")
                    c12.metric("Correlation", f"{beta_alpha['correlation']:.3f}")

    with rtab2:
        st.subheader("Monte Carlo Simulation")
        mc_market = st.selectbox("Market", ["KR", "US"], key="mc_market")
        mc_ticker = st.text_input("Ticker", value="005930" if mc_market == "KR" else "AAPL", key="mc_ticker")
        mc_sims = st.number_input("Simulations", 100, 5000, 1000, 100, key="mc_sims")
        mc_days = st.number_input("Forecast Days", 5, 252, 30, key="mc_days")
        mc_conf = st.selectbox("Confidence", [0.90, 0.95, 0.99], index=1, key="mc_conf")

        if st.button("Run Monte Carlo", type="primary", key="btn_mc"):
            with st.spinner(f"Running {mc_sims} simulations..."):
                df_mc = fetch_stock_fn(mc_ticker, mc_market, "1y")

            if df_mc.empty:
                st.error("Failed to fetch data.")
            else:
                from analysis.monte_carlo import run_monte_carlo

                mc = run_monte_carlo(df_mc, mc_sims, mc_days, mc_conf)

                c1, c2 = st.columns(2)
                c1.metric("Current Price", f"{mc['current_price']:,.0f}")
                c2.metric("Expected Price", f"{mc['mean_price']:,.0f}", f"{mc['expected_return']:+.2f}%")

    with rtab3:
        st.subheader("Efficient Frontier (Markowitz Optimization)")
        ef_market = st.selectbox("Market", ["KR", "US"], key="ef_market")
        if ef_market == "KR":
            ef_tickers = st.text_input("Tickers (comma-separated)", "005930, 000660, 035420, 051910, 006400", key="ef_tickers")
        else:
            ef_tickers = st.text_input("Tickers (comma-separated)", "AAPL, MSFT, GOOGL, NVDA, AMZN", key="ef_tickers")
        ef_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="ef_period")

        if st.button("Calculate Efficient Frontier", type="primary", key="btn_ef"):
            from analysis.risk import calc_efficient_frontier

            tickers = [t.strip() for t in ef_tickers.split(",") if t.strip()]
            returns_dict = {}
            for t in tickers:
                d = fetch_stock_fn(t, ef_market, ef_period)
                if not d.empty:
                    returns_dict[t] = d["Close"].pct_change()
            if len(returns_dict) < 2:
                st.error("Need at least 2 valid tickers.")
            else:
                ef = calc_efficient_frontier(pd.DataFrame(returns_dict).dropna(), 3000)
                if "error" in ef:
                    st.error(ef["error"])
                else:
                    st.success("Efficient frontier calculation completed.")

    with rtab4:
        st.subheader("Leverage/Margin Simulator")
        lev_market = st.selectbox("Market", ["KR", "US"], key="lev_market")
        lev_ticker = st.text_input("Ticker", value="005930" if lev_market == "KR" else "AAPL", key="lev_ticker")
        lev_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="lev_period")
        leverage = st.slider("Leverage Multiplier", min_value=1.0, max_value=5.0, value=2.0, step=0.5, key="lev_mult")

        if st.button("Run Leverage Simulation", type="primary", key="btn_lev"):
            import numpy as np

            df_lev = fetch_stock_fn(lev_ticker, lev_market, lev_period)
            if df_lev.empty:
                st.error("Failed to fetch data.")
            else:
                returns = cast(pd.Series, df_lev["Close"].pct_change().dropna())
                leveraged_returns = cast(pd.Series, returns * leverage)
                equity_1x = pd.Series(np.cumprod(1.0 + returns.to_numpy()), index=returns.index)
                equity_lev = pd.Series(np.cumprod(1.0 + leveraged_returns.to_numpy()), index=leveraged_returns.index)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=equity_1x.index, y=equity_1x, name="1x"))
                fig.add_trace(go.Scatter(x=equity_lev.index, y=equity_lev, name=f"{leverage:.1f}x"))
                st.plotly_chart(fig, use_container_width=True)

    show_legal_disclaimer()
