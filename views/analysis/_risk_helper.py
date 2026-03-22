from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config.auth import is_pro
from config.styles import show_legal_disclaimer
from data.fetcher import fetch_stock


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _render_monte_carlo_result(mc_result: dict[str, Any]) -> None:
    mc = mc_result.get("data", {})
    if not isinstance(mc, dict):
        return
    if "error" in mc:
        st.error(str(mc.get("error") or "Monte Carlo 계산 실패"))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", f"{_to_float(mc.get('current_price')):,.0f}")
    c2.metric(
        "Expected Price",
        f"{_to_float(mc.get('mean_price')):,.0f}",
        f"{_to_float(mc.get('expected_return')):+.2f}%",
    )
    c3.metric("Loss Prob (<0)", f"{_to_float(mc.get('prob_loss')):.1f}%")
    c4.metric("Gain Prob (>0)", f"{_to_float(mc.get('prob_profit')):.1f}%")

    simulations = mc.get("simulations")
    if isinstance(simulations, pd.DataFrame) and not simulations.empty:
        fig_mc = go.Figure()
        sampled = simulations.iloc[:, : min(100, simulations.shape[1])]
        for idx, col in enumerate(sampled.columns):
            fig_mc.add_trace(
                go.Scatter(
                    x=sampled.index,
                    y=sampled[col],
                    mode="lines",
                    line=dict(width=1),
                    opacity=0.15,
                    showlegend=False,
                    name=f"path_{idx}",
                )
            )

        percentiles = mc.get("percentiles")
        if isinstance(percentiles, pd.DataFrame) and not percentiles.empty:
            known = {"mean", "p50", "p95", "p5"}
            if not known.intersection(set(percentiles.columns.astype(str).tolist())):
                st.warning("Monte Carlo 백분위 데이터 형식이 예상과 달라 요약선 일부가 생략됩니다.")
            for name, color in [("mean", "#FFFFFF"), ("p50", "#00D4AA"), ("p95", "#38BDF8"), ("p5", "#F97316")]:
                if name in percentiles.columns:
                    fig_mc.add_trace(
                        go.Scatter(
                            x=percentiles.index,
                            y=percentiles[name],
                            mode="lines",
                            line=dict(width=3 if name in {"mean", "p50"} else 2, color=color),
                            name=name.upper(),
                        )
                    )

        fig_mc.update_layout(
            title=f"Monte Carlo Price Paths ({mc_result.get('ticker', '-')})",
            xaxis_title="Step",
            yaxis_title="Price",
            template="plotly_dark",
            height=520,
            hovermode="x unified",
        )
        st.plotly_chart(fig_mc, use_container_width=True)

    returns_dist = mc.get("returns_dist")
    if isinstance(returns_dist, pd.Series) and not returns_dist.empty:
        fig_hist = go.Figure(
            data=[go.Histogram(x=returns_dist.values, nbinsx=40, marker_color="#00D4AA", opacity=0.85)]
        )
        fig_hist.update_layout(
            title="Simulation Return Distribution (%)",
            xaxis_title="Return (%)",
            yaxis_title="Count",
            template="plotly_dark",
            height=360,
        )
        st.plotly_chart(fig_hist, use_container_width=True)


def _render_efficient_frontier_result(ef_result: dict[str, Any]) -> None:
    ef_data = ef_result.get("data", {})
    if not isinstance(ef_data, dict):
        return
    if "error" in ef_data:
        st.error(str(ef_data.get("error") or "효율적 프론티어 계산 실패"))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Max Sharpe Return", f"{_to_float(ef_data.get('max_sharpe_return')):.2f}%")
    c2.metric("Max Sharpe Vol", f"{_to_float(ef_data.get('max_sharpe_vol')):.2f}%")
    c3.metric("Min Vol Return", f"{_to_float(ef_data.get('min_vol_return')):.2f}%")
    c4.metric("Min Vol Vol", f"{_to_float(ef_data.get('min_vol_vol')):.2f}%")

    vols, rets, sharpes = ef_data.get("volatility"), ef_data.get("returns"), ef_data.get("sharpe")
    if vols is not None and rets is not None and sharpes is not None:
        fig_ef = go.Figure()
        fig_ef.add_trace(
            go.Scatter(
                x=vols,
                y=rets,
                mode="markers",
                marker=dict(color=sharpes, colorscale="Viridis", size=6, colorbar=dict(title="Sharpe")),
                name="Portfolios",
            )
        )
        fig_ef.add_trace(
            go.Scatter(
                x=[_to_float(ef_data.get("max_sharpe_vol"))],
                y=[_to_float(ef_data.get("max_sharpe_return"))],
                mode="markers",
                marker=dict(color="#F97316", size=14, symbol="star"),
                name="Max Sharpe",
            )
        )
        fig_ef.add_trace(
            go.Scatter(
                x=[_to_float(ef_data.get("min_vol_vol"))],
                y=[_to_float(ef_data.get("min_vol_return"))],
                mode="markers",
                marker=dict(color="#38BDF8", size=12, symbol="diamond"),
                name="Min Vol",
            )
        )
        fig_ef.update_layout(
            title="Efficient Frontier",
            xaxis_title="Volatility (%)",
            yaxis_title="Expected Return (%)",
            template="plotly_dark",
            height=520,
            hovermode="closest",
        )
        st.plotly_chart(fig_ef, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.markdown("**Max Sharpe Weights (%)**")
        ms_rows = [{"Ticker": k, "Weight(%)": v} for k, v in dict(ef_data.get("max_sharpe_weights", {})).items()]
        st.dataframe(pd.DataFrame(ms_rows), use_container_width=True, hide_index=True)
    with right:
        st.markdown("**Min Vol Weights (%)**")
        mv_rows = [{"Ticker": k, "Weight(%)": v} for k, v in dict(ef_data.get("min_vol_weights", {})).items()]
        st.dataframe(pd.DataFrame(mv_rows), use_container_width=True, hide_index=True)


def render_risk_tab(user: dict[str, Any]) -> None:
    """Render the risk analysis tab."""
    st.header("Risk Analysis & Monte Carlo")
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
                df = fetch_stock(ticker, market, period)
                df_bench = fetch_stock(benchmark, market, period)
            if df.empty:
                st.error("Failed to fetch data.")
            else:
                from analysis.risk import calc_beta_alpha, calc_risk_metrics

                returns = cast(pd.Series, df["Close"].pct_change().dropna())
                metrics = calc_risk_metrics(returns)
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
                df_mc = fetch_stock(mc_ticker, mc_market, "1y")
            if df_mc.empty:
                st.error("Failed to fetch data.")
            else:
                from analysis.monte_carlo import run_monte_carlo

                mc = run_monte_carlo(df_mc, mc_sims, mc_days, mc_conf)
                sims = mc.get("simulations") if isinstance(mc, dict) else None
                if isinstance(sims, pd.DataFrame) and not sims.empty:
                    mc["simulations"] = sims.iloc[:, : min(300, sims.shape[1])].astype("float32")
                st.session_state["risk_mc_result"] = {
                    "ticker": mc_ticker,
                    "market": mc_market,
                    "days": int(mc_days),
                    "confidence": float(mc_conf),
                    "data": mc,
                }
        if isinstance(st.session_state.get("risk_mc_result"), dict):
            _render_monte_carlo_result(cast(dict[str, Any], st.session_state["risk_mc_result"]))

    with rtab3:
        st.subheader("Efficient Frontier (Markowitz Optimization)")
        ef_market = st.selectbox("Market", ["KR", "US"], key="ef_market")
        ef_default = "005930, 000660, 035420, 051910, 006400" if ef_market == "KR" else "AAPL, MSFT, GOOGL, NVDA, AMZN"
        ef_tickers = st.text_input("Tickers (comma-separated)", ef_default, key="ef_tickers")
        ef_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="ef_period")
        if st.button("Calculate Efficient Frontier", type="primary", key="btn_ef"):
            from analysis.risk import calc_efficient_frontier

            tickers = [t.strip() for t in ef_tickers.split(",") if t.strip()]
            returns_dict: dict[str, pd.Series] = {}
            for t in tickers:
                data = fetch_stock(t, ef_market, ef_period)
                if not data.empty:
                    returns_dict[t] = cast(pd.Series, data["Close"].pct_change())
            if len(returns_dict) < 2:
                st.error("Need at least 2 valid tickers.")
            else:
                st.session_state["risk_ef_result"] = {
                    "tickers": list(returns_dict.keys()),
                    "market": ef_market,
                    "period": ef_period,
                    "data": calc_efficient_frontier(pd.DataFrame(returns_dict).dropna(), 3000),
                }
        if isinstance(st.session_state.get("risk_ef_result"), dict):
            _render_efficient_frontier_result(cast(dict[str, Any], st.session_state["risk_ef_result"]))

    with rtab4:
        st.subheader("Leverage/Margin Simulator")
        lev_market = st.selectbox("Market", ["KR", "US"], key="lev_market")
        lev_ticker = st.text_input("Ticker", value="005930" if lev_market == "KR" else "AAPL", key="lev_ticker")
        lev_period = st.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="lev_period")
        leverage = st.slider("Leverage Multiplier", min_value=1.0, max_value=5.0, value=2.0, step=0.5, key="lev_mult")
        if st.button("Run Leverage Simulation", type="primary", key="btn_lev"):
            import numpy as np

            df_lev = fetch_stock(lev_ticker, lev_market, lev_period)
            if df_lev.empty:
                st.error("Failed to fetch data.")
            else:
                returns = cast(pd.Series, df_lev["Close"].pct_change().dropna())
                lev_returns = cast(pd.Series, returns * leverage)
                equity_1x = pd.Series(np.cumprod(1.0 + returns.to_numpy()), index=returns.index)
                equity_lev = pd.Series(np.cumprod(1.0 + lev_returns.to_numpy()), index=lev_returns.index)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=equity_1x.index, y=equity_1x, name="1x"))
                fig.add_trace(go.Scatter(x=equity_lev.index, y=equity_lev, name=f"{leverage:.1f}x"))
                st.plotly_chart(fig, use_container_width=True)

    show_legal_disclaimer()
