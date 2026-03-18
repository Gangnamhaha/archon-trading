from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis.backtest import STRATEGIES, BacktestEngine, optimize_strategy_params
from config.auth import is_paid, is_pro
from config.styles import show_legal_disclaimer
from data.fetcher import fetch_stock
from data.news import NEWS_SOURCES, fetch_and_analyze, get_market_sentiment


def render_news_tab(user: dict[str, Any]) -> None:
    """Render the news & sentiment analysis tab."""
    st.header("News & Sentiment Analysis")

    _user_is_paid = is_paid(user)
    _max_free_articles = 5

    st.sidebar.header("Settings")
    sources = st.sidebar.multiselect(
        "News Sources",
        list(NEWS_SOURCES.keys()),
        default=list(NEWS_SOURCES.keys())[:4],
        key="news_sources",
    )
    keyword = st.sidebar.text_input("Keyword Filter", placeholder="e.g. Samsung, NVIDIA", key="news_keyword")

    if not _user_is_paid:
        st.sidebar.info(f"🔒 Free 플랜: 하루 {_max_free_articles}건 조회 제한")

    if st.sidebar.button("Fetch News", type="primary", use_container_width=True, key="news_fetch"):
        with st.spinner("Fetching news and analyzing sentiment..."):
            keyword_value = keyword.strip()
            sentiment_summary = get_market_sentiment(sources)
            news_df = fetch_and_analyze(sources, keyword_value)

        if not _user_is_paid and not news_df.empty and len(news_df) > _max_free_articles:
            news_df = news_df.head(_max_free_articles)
            st.warning(f"🔒 Free 플랜: 상위 {_max_free_articles}건만 표시됩니다. Plus 업그레이드 시 전체 조회 가능.")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Market Mood", sentiment_summary["overall"])
        col2.metric("Positive", f"{sentiment_summary['positive_pct']}%")
        col3.metric("Negative", f"{sentiment_summary['negative_pct']}%")
        col4.metric("Total Articles", sentiment_summary["total"])

        if not news_df.empty:
            import plotly.express as px
            sentiment_counts = news_df["감성"].value_counts()
            fig_pie = px.pie(values=sentiment_counts.values, names=sentiment_counts.index, title="Sentiment Distribution")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("No articles found.")
    else:
        st.info("Select news sources and click 'Fetch News'.")


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
                from typing import cast
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
            from typing import cast

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


def render_strategy_optimizer(initial_capital: int) -> None:
    if "last_backtest_df" not in st.session_state:
        return

    with st.expander("🔧 전략 파라미터 자동 최적화", expanded=False):
        st.caption("💎 Pro 전용 기능")

        optimize_param_grids = {
            "RSI 전략": {
                "buy_threshold": [20, 25, 30, 35],
                "sell_threshold": [65, 70, 75, 80],
            },
            "골든크로스/데드크로스": {
                "short": [3, 5, 10],
                "long": [15, 20, 30, 60],
            },
            "볼린저밴드 전략": {
                "period": [15, 20, 25],
                "std_dev": [1.5, 2.0, 2.5],
            },
            "변동성 돌파 전략": {
                "k": [0.3, 0.4, 0.5, 0.6, 0.7],
                "stop_loss": [1.5, 2.0, 3.0],
            },
        }

        optimize_candidates = list(optimize_param_grids.keys())
        saved_strategy = st.session_state.get("last_backtest_strategy")
        default_strategy = saved_strategy if isinstance(saved_strategy, str) else optimize_candidates[0]
        default_idx = optimize_candidates.index(default_strategy) if default_strategy in optimize_candidates else 0
        optimize_strategy_name = st.selectbox(
            "최적화 대상 전략",
            optimize_candidates,
            index=default_idx,
            key="optimize_strategy_name",
        ) or optimize_candidates[default_idx]

        if st.button("최적화 시작", use_container_width=True, key="run_strategy_optimizer"):
            progress_bar = st.progress(0)
            progress_bar.progress(10)

            optimization = optimize_strategy_params(
                st.session_state["last_backtest_df"],
                optimize_strategy_name,
                optimize_param_grids.get(optimize_strategy_name, {}),
                initial_capital=initial_capital,
            )
            progress_bar.progress(100)

            if not optimization.get("all_results"):
                st.warning("최적화 가능한 결과가 없습니다. 데이터 기간이나 전략을 변경해보세요.")
                return

            best_params = optimization.get("best_params", {})
            best_sharpe = float(optimization.get("best_sharpe", 0.0))
            st.metric("최고 샤프 비율", f"{best_sharpe:.2f}")
            st.markdown("**최적 파라미터**")
            st.json(best_params)

            rows = []
            for item in optimization["all_results"][:5]:
                row = dict(item.get("params", {}))
                row["샤프"] = round(float(item.get("sharpe", 0)), 2)
                row["총 수익률 (%)"] = round(float(item.get("total_return", 0)), 2)
                row["MDD (%)"] = round(float(item.get("mdd", 0)), 2)
                row["거래 횟수"] = int(item.get("trades", 0))
                rows.append(row)

            if rows:
                st.markdown("**상위 5개 조합**")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_strategy_comparison(
    ticker: str,
    market_code: str,
    period: str,
    initial_capital: int,
    commission: float,
) -> None:
    st.markdown("---")
    st.subheader("전략 비교")
    if not st.button("모든 전략 비교 실행", use_container_width=True, key="bt_compare_all"):
        return

    with st.spinner("모든 전략 비교 중..."):
        df = fetch_stock(ticker, market_code, period)
        if df.empty:
            st.error("데이터를 가져올 수 없습니다.")
            return

        fig_compare = go.Figure()
        results_table = []

        for name, strategy_func in STRATEGIES.items():
            signals = strategy_func(df)
            engine = BacktestEngine(df, initial_capital, commission / 100)
            res = engine.run(signals)
            eq = engine.get_equity_curve()

            if not eq.empty:
                fig_compare.add_trace(go.Scatter(x=eq.index, y=eq["equity"], name=name, mode="lines"))

            results_table.append(
                {
                    "전략": name,
                    "총 수익률 (%)": res.get("총 수익률 (%)", 0),
                    "연환산 (%)": res.get("연환산 수익률 (%)", 0),
                    "MDD (%)": res.get("최대 낙폭 MDD (%)", 0),
                    "샤프": res.get("샤프 비율", 0),
                    "소르티노": res.get("소르티노 비율", 0),
                    "칼마": res.get("칼마 비율", 0),
                    "승률 (%)": res.get("승률 (%)", 0),
                    "손익비": res.get("손익비 (Profit Factor)", 0),
                    "거래 횟수": res.get("총 거래 횟수", 0),
                }
            )

        buy_hold = initial_capital * (df["Close"] / df["Close"].iloc[0])
        fig_compare.add_trace(
            go.Scatter(x=df.index, y=buy_hold, name="Buy & Hold", line=dict(dash="dash", color="black"))
        )

        fig_compare.update_layout(
            title="전략별 자산 추이 비교",
            height=500,
            xaxis_title="날짜",
            yaxis_title="자산 (원)",
            hovermode="x unified",
            template="plotly_dark",
        )
        st.plotly_chart(fig_compare, use_container_width=True)

        st.dataframe(pd.DataFrame(results_table), use_container_width=True)
