import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from data.fetcher import fetch_stock
from analysis.risk import calc_risk_metrics, calc_var, calc_beta_alpha, calc_efficient_frontier
from analysis.monte_carlo import run_monte_carlo
from config.styles import inject_pro_css, show_legal_disclaimer
from config.auth import require_pro

st.set_page_config(page_title="Risk Analysis", page_icon="", layout="wide")
require_pro()
inject_pro_css()
st.title("Risk Analysis & Monte Carlo")

tab1, tab2, tab3, tab4 = st.tabs(["Risk Metrics", "Monte Carlo Simulation", "Efficient Frontier", "Leverage Simulator"])

with tab1:
    st.sidebar.header("Risk Settings")
    market = st.sidebar.selectbox("Market", ["KR", "US"], key="risk_market")
    ticker = st.sidebar.text_input("Ticker", value="005930" if market == "KR" else "AAPL", key="risk_ticker")
    benchmark = st.sidebar.text_input("Benchmark", value="069500" if market == "KR" else "SPY", key="benchmark")
    period = st.sidebar.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="risk_period")

    if st.sidebar.button("Analyze Risk", type="primary", key="btn_risk"):
        with st.spinner("Calculating risk metrics..."):
            df = fetch_stock(ticker, market, period)
            df_bench = fetch_stock(benchmark, market, period)

        if df.empty:
            st.error("Failed to fetch data.")
        else:
            returns = df["Close"].pct_change().dropna()
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
                bench_returns = df_bench["Close"].pct_change().dropna()
                beta_alpha = calc_beta_alpha(returns, bench_returns)
                c9, c10, c11, c12 = st.columns(4)
                c9.metric("Beta", f"{beta_alpha['beta']:.3f}")
                c10.metric("Alpha (%)", f"{beta_alpha['alpha']:.3f}")
                c11.metric("R-Squared", f"{beta_alpha['r_squared']:.3f}")
                c12.metric("Correlation", f"{beta_alpha['correlation']:.3f}")

            st.markdown("---")

            col1, col2 = st.columns(2)
            with col1:
                fig_dist = go.Figure()
                fig_dist.add_trace(go.Histogram(
                    x=returns * 100, nbinsx=50, name="Daily Returns",
                    marker_color="#00D4AA", opacity=0.7
                ))
                var_95 = np.percentile(returns, 5) * 100
                fig_dist.add_vline(x=var_95, line_dash="dash", line_color="red",
                                   annotation_text=f"VaR 95%: {var_95:.2f}%")
                fig_dist.update_layout(
                    title="Return Distribution", template="plotly_dark",
                    xaxis_title="Return (%)", yaxis_title="Frequency", height=400
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            with col2:
                equity = (1 + returns).cumprod()
                rolling_max = equity.cummax()
                drawdown = (equity - rolling_max) / rolling_max * 100
                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=drawdown.index, y=drawdown, fill="tozeroy",
                    fillcolor="rgba(255,107,107,0.3)", line=dict(color="#FF6B6B"),
                    name="Drawdown"
                ))
                fig_dd.update_layout(
                    title="Drawdown Chart", template="plotly_dark",
                    yaxis_title="Drawdown (%)", height=400
                )
                st.plotly_chart(fig_dd, use_container_width=True)

with tab2:
    st.subheader("Monte Carlo Simulation")
    mc_market = st.selectbox("Market", ["KR", "US"], key="mc_market")
    mc_ticker = st.text_input("Ticker", value="005930" if mc_market == "KR" else "AAPL", key="mc_ticker")

    col1, col2, col3 = st.columns(3)
    mc_sims = col1.number_input("Simulations", 100, 5000, 1000, 100)
    mc_days = col2.number_input("Forecast Days", 5, 252, 30)
    mc_conf = col3.selectbox("Confidence", [0.90, 0.95, 0.99], index=1)

    if st.button("Run Monte Carlo", type="primary", key="btn_mc"):
        with st.spinner(f"Running {mc_sims} simulations..."):
            df_mc = fetch_stock(mc_ticker, mc_market, "1y")

        if df_mc.empty:
            st.error("Failed to fetch data.")
        else:
            mc = run_monte_carlo(df_mc, mc_sims, mc_days, mc_conf)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Price", f"{mc['current_price']:,.0f}")
            c2.metric("Expected Price", f"{mc['mean_price']:,.0f}", f"{mc['expected_return']:+.2f}%")
            c3.metric("Profit Probability", f"{mc['prob_profit']:.1f}%")
            c4.metric(f"CI {mc_conf*100:.0f}%", f"{mc['lower_bound']:,.0f} ~ {mc['upper_bound']:,.0f}")

            st.markdown("---")

            fig_mc = go.Figure()
            sample_paths = min(100, mc_sims)
            for i in range(sample_paths):
                fig_mc.add_trace(go.Scatter(
                    y=mc["simulations"][:, i], mode="lines",
                    line=dict(width=0.3, color="rgba(0,212,170,0.15)"),
                    showlegend=False
                ))
            for p_name, color in [("p5", "#FF6B6B"), ("p50", "#FFFFFF"), ("p95", "#00D4AA")]:
                fig_mc.add_trace(go.Scatter(
                    y=mc["percentiles"][p_name], mode="lines",
                    name=p_name.upper(), line=dict(width=2, color=color)
                ))
            fig_mc.update_layout(
                title=f"Monte Carlo Simulation ({mc_sims} paths, {mc_days} days)",
                template="plotly_dark", height=500,
                xaxis_title="Days", yaxis_title="Price"
            )
            st.plotly_chart(fig_mc, use_container_width=True)

            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=mc["returns_dist"], nbinsx=50, name="Return Distribution",
                marker_color="#00D4AA", opacity=0.7
            ))
            fig_hist.add_vline(x=0, line_color="white", line_dash="dash")
            fig_hist.update_layout(
                title="Simulated Return Distribution (%)",
                template="plotly_dark", height=350,
                xaxis_title="Return (%)", yaxis_title="Frequency"
            )
            st.plotly_chart(fig_hist, use_container_width=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Best Case", f"{mc['best_case']:,.0f}")
            c2.metric("Worst Case", f"{mc['worst_case']:,.0f}")
            c3.metric("10%+ Gain Prob", f"{mc['prob_gain_10']:.1f}%")

with tab3:
    st.subheader("Efficient Frontier (Markowitz Optimization)")
    ef_market = st.selectbox("Market", ["KR", "US"], key="ef_market")
    if ef_market == "KR":
        ef_tickers = st.text_input("Tickers (comma-separated)", "005930, 000660, 035420, 051910, 006400", key="ef_tickers")
    else:
        ef_tickers = st.text_input("Tickers (comma-separated)", "AAPL, MSFT, GOOGL, NVDA, AMZN", key="ef_tickers")
    ef_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="ef_period")

    if st.button("Calculate Efficient Frontier", type="primary", key="btn_ef"):
        tickers = [t.strip() for t in ef_tickers.split(",") if t.strip()]
        if len(tickers) < 2:
            st.error("At least 2 tickers required.")
        else:
            returns_dict = {}
            with st.spinner("Fetching data..."):
                for t in tickers:
                    d = fetch_stock(t, ef_market, ef_period)
                    if not d.empty:
                        returns_dict[t] = d["Close"].pct_change()

            if len(returns_dict) < 2:
                st.error("Need at least 2 valid tickers.")
            else:
                returns_df = pd.DataFrame(returns_dict).dropna()
                with st.spinner("Optimizing portfolios..."):
                    ef = calc_efficient_frontier(returns_df, 3000)

                if "error" in ef:
                    st.error(ef["error"])
                else:
                    fig_ef = go.Figure()
                    fig_ef.add_trace(go.Scatter(
                        x=ef["volatility"], y=ef["returns"],
                        mode="markers",
                        marker=dict(size=3, color=ef["sharpe"], colorscale="Viridis",
                                    showscale=True, colorbar=dict(title="Sharpe")),
                        name="Portfolios"
                    ))
                    fig_ef.add_trace(go.Scatter(
                        x=[ef["max_sharpe_vol"]], y=[ef["max_sharpe_return"]],
                        mode="markers", name="Max Sharpe",
                        marker=dict(size=15, color="red", symbol="star")
                    ))
                    fig_ef.add_trace(go.Scatter(
                        x=[ef["min_vol_vol"]], y=[ef["min_vol_return"]],
                        mode="markers", name="Min Volatility",
                        marker=dict(size=15, color="blue", symbol="star")
                    ))
                    fig_ef.update_layout(
                        title="Efficient Frontier",
                        xaxis_title="Volatility (%)", yaxis_title="Return (%)",
                        template="plotly_dark", height=500
                    )
                    st.plotly_chart(fig_ef, use_container_width=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Max Sharpe Portfolio**")
                        st.metric("Return", f"{ef['max_sharpe_return']:.2f}%")
                        st.metric("Volatility", f"{ef['max_sharpe_vol']:.2f}%")
                        weights_df = pd.DataFrame([ef["max_sharpe_weights"]]).T
                        weights_df.columns = ["Weight (%)"]
                        st.dataframe(weights_df)

                    with col2:
                        st.markdown("**Min Volatility Portfolio**")
                        st.metric("Return", f"{ef['min_vol_return']:.2f}%")
                        st.metric("Volatility", f"{ef['min_vol_vol']:.2f}%")
                        weights_df2 = pd.DataFrame([ef["min_vol_weights"]]).T
                        weights_df2.columns = ["Weight (%)"]
                        st.dataframe(weights_df2)

with tab4:
    st.subheader("Leverage/Margin Simulator")

    lev_market = st.selectbox("Market", ["KR", "US"], key="lev_market")
    lev_ticker = st.text_input("Ticker", value="005930" if lev_market == "KR" else "AAPL", key="lev_ticker")
    lev_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="lev_period")
    leverage = st.slider("Leverage Multiplier", min_value=1.0, max_value=5.0, value=2.0, step=0.5, key="lev_mult")

    if st.button("Run Leverage Simulation", type="primary", key="btn_lev"):
        with st.spinner("Running leverage simulation..."):
            df_lev = fetch_stock(lev_ticker, lev_market, lev_period)

        if df_lev.empty:
            st.error("Failed to fetch data.")
        else:
            returns = df_lev["Close"].pct_change().dropna()
            leveraged_returns = returns * leverage

            equity_1x = (1 + returns).cumprod()
            equity_lev = (1 + leveraged_returns).cumprod()

            def _calc_metrics(ret_series: pd.Series, equity_series: pd.Series) -> dict:
                periods = len(ret_series)
                final_value = equity_series.iloc[-1] if not equity_series.empty else 1.0
                if periods > 0 and final_value > 0:
                    annual_return = (final_value ** (252 / periods) - 1) * 100
                else:
                    annual_return = -100.0

                annual_vol = ret_series.std() * np.sqrt(252) * 100 if periods > 1 else 0.0
                rolling_max = equity_series.cummax()
                drawdown = (equity_series - rolling_max) / rolling_max
                mdd = drawdown.min() * 100 if not drawdown.empty else 0.0

                if ret_series.std() > 0:
                    sharpe = (ret_series.mean() - 0.03 / 252) / ret_series.std() * np.sqrt(252)
                else:
                    sharpe = 0.0

                return {
                    "연수익률(%)": annual_return,
                    "연변동성(%)": annual_vol,
                    "MDD(%)": mdd,
                    "샤프비율": sharpe,
                }

            metrics_1x = _calc_metrics(returns, equity_1x)
            metrics_lev = _calc_metrics(leveraged_returns, equity_lev)

            compare_df = pd.DataFrame([
                {
                    "구분": "1x",
                    "연수익률(%)": metrics_1x["연수익률(%)"],
                    "연변동성(%)": metrics_1x["연변동성(%)"],
                    "MDD(%)": metrics_1x["MDD(%)"],
                    "샤프비율": metrics_1x["샤프비율"],
                },
                {
                    "구분": f"{leverage:.1f}x",
                    "연수익률(%)": metrics_lev["연수익률(%)"],
                    "연변동성(%)": metrics_lev["연변동성(%)"],
                    "MDD(%)": metrics_lev["MDD(%)"],
                    "샤프비율": metrics_lev["샤프비율"],
                },
            ])

            st.dataframe(
                compare_df.style.format({
                    "연수익률(%)": "{:.2f}",
                    "연변동성(%)": "{:.2f}",
                    "MDD(%)": "{:.2f}",
                    "샤프비율": "{:.3f}",
                }),
                use_container_width=True,
            )

            fig_lev = go.Figure()
            fig_lev.add_trace(go.Scatter(
                x=equity_1x.index, y=equity_1x,
                name="1x Equity", line=dict(color="#00D4AA", width=2)
            ))
            fig_lev.add_trace(go.Scatter(
                x=equity_lev.index, y=equity_lev,
                name=f"{leverage:.1f}x Equity", line=dict(color="#FF6B6B", width=2)
            ))
            fig_lev.update_layout(
                title="Equity Curve Comparison",
                template="plotly_dark",
                height=450,
                xaxis_title="Date",
                yaxis_title="Equity (Start=1.0)",
                hovermode="x unified",
            )
            st.plotly_chart(fig_lev, use_container_width=True)

            st.warning(
                f"⚠️ 레버리지는 수익과 손실을 모두 증폭합니다. {leverage:.1f}x 레버리지 시 -{100 / leverage:.0f}% 하락으로 원금 전액 손실 가능."
            )

            st.markdown("---")
            st.markdown("**Liquidation Price Calculator**")
            entry_price = st.number_input("Entry Price", min_value=0.01, value=float(df_lev["Close"].iloc[-1]), step=0.01, key="lev_entry")
            liq_price = entry_price * (1 - 1 / leverage)
            drop_pct = 100 / leverage
            st.metric("Estimated Margin Call Price", f"{liq_price:,.2f}", f"-{drop_pct:.2f}% from entry")

show_legal_disclaimer()
