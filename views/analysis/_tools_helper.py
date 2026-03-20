from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis.backtest import STRATEGIES, BacktestEngine, optimize_strategy_params
from config.auth import is_paid
from data.fetcher import fetch_stock
from data.news import NEWS_SOURCES, fetch_and_analyze, get_market_sentiment
from views.analysis._risk_helper import render_risk_tab


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
