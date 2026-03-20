# pyright: basic
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis.recommender import recommend_for_portfolio
from config.auth import is_paid, is_pro, require_auth
from config.styles import inject_pro_css
from data.database import add_stock, get_portfolio, remove_stock
from portfolio.tracker import PortfolioTracker
from views._portfolio_helper import (
    render_fx_crypto_alert_tabs,
    render_holdings_table,
    render_pro_analytics,
    render_rebalancing_section,
)


def _score_style(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return ""
    if score >= 40:
        return "color: #00c853; font-weight: 700"
    if score >= 20:
        return "color: #4caf50; font-weight: 700"
    if score >= 0:
        return "color: #ffa726; font-weight: 700"
    return "color: #ef5350; font-weight: 700"


def _diversification_style(value: Any) -> str:
    try:
        div_effect = float(value)
    except (TypeError, ValueError):
        return ""
    if div_effect >= 1.0:
        return "color: #00c853; font-weight: 700"
    if div_effect >= 0.7:
        return "color: #8bc34a; font-weight: 700"
    if div_effect >= 0.4:
        return "color: #ffa726; font-weight: 700"
    return "color: #ef5350; font-weight: 700"


def _extract_kr_holdings_tickers(portfolio_df: pd.DataFrame) -> list[str]:
    if portfolio_df.empty or "ticker" not in portfolio_df.columns:
        return []

    if "market" in portfolio_df.columns:
        kr_df = portfolio_df[portfolio_df["market"].astype(str).str.upper() == "KR"]
    else:
        kr_df = portfolio_df
    return sorted({str(ticker).strip() for ticker in kr_df["ticker"].tolist() if str(ticker).strip()})


def _render_portfolio_recommendations(portfolio_df: pd.DataFrame, holdings: pd.DataFrame) -> None:
    with st.expander("🏆 AI 종목추천", expanded=False):
        holdings_tickers = _extract_kr_holdings_tickers(portfolio_df)
        total_count = len(portfolio_df) if not portfolio_df.empty else 0
        kr_count = len(holdings_tickers)

        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("전체 보유종목", f"{total_count}개")
        metric_col2.metric("국내 종목", f"{kr_count}개")

        top_weight_text = "-"
        if not holdings.empty and "평가금액" in holdings.columns and "name" in holdings.columns:
            weighted_rows: list[tuple[str, float]] = []
            for _, row in holdings.loc[:, ["name", "평가금액"]].iterrows():
                try:
                    amount = float(row["평가금액"])
                except (TypeError, ValueError):
                    continue
                if amount <= 0:
                    continue
                weighted_rows.append((str(row["name"]), amount))

            total_value = float(sum(amount for _, amount in weighted_rows))
            if total_value > 0 and weighted_rows:
                weights = [(name, amount / total_value * 100) for name, amount in weighted_rows]
                weights.sort(key=lambda item: item[1], reverse=True)
                top3 = weights[:3]
                top_weight_text = f"{top3[0][1]:.1f}%"
                top_line = ", ".join(f"{name} {weight:.1f}%" for name, weight in top3)
                st.caption(f"집중도(상위 비중): {top_line}")
        metric_col3.metric("최대 집중도", top_weight_text)

        ctrl_col1, ctrl_col2 = st.columns(2)
        rec_market = str(ctrl_col1.selectbox("추천 시장", ["KOSPI", "KOSDAQ"], key="portfolio_rec_market") or "KOSPI")
        top_n = int(ctrl_col2.selectbox("추천 종목 수", [5, 10, 15, 20], index=1, key="portfolio_rec_top_n") or 10)
        run_recommend = st.button("포트폴리오 맞춤 추천 실행", type="primary", use_container_width=True, key="portfolio_recommend_run")

        run_params = {
            "holdings": tuple(holdings_tickers),
            "market": rec_market,
            "top_n": top_n,
        }

        if run_recommend:
            with st.spinner("포트폴리오 맞춤 추천 분석 중..."):
                result_df = recommend_for_portfolio(holdings_tickers, market=rec_market, top_n=top_n)
            st.session_state["portfolio_recommendations"] = result_df
            st.session_state["portfolio_recommendations_params"] = run_params

        cached_df = st.session_state.get("portfolio_recommendations")
        cached_params = st.session_state.get("portfolio_recommendations_params")
        if not isinstance(cached_df, pd.DataFrame) or cached_params != run_params:
            if not holdings_tickers:
                st.info("보유 국내 종목이 없어 일반 추천 모드로 동작합니다. 버튼을 눌러 추천을 실행하세요.")
            return

        if not holdings_tickers:
            st.info("포트폴리오가 비어 있어 시장 기준 상위 종목을 추천합니다.")

        if cached_df.empty:
            st.warning("추천 결과가 없습니다. 시장을 변경하거나 잠시 후 다시 시도하세요.")
            return

        styled_df = cached_df.style.map(_score_style, subset=["종합점수"]).map(
            _diversification_style,
            subset=["분산효과"],
        )
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        st.markdown("##### TOP 3 핵심 추천")
        top3_cols = st.columns(3)
        for idx, (_, row) in enumerate(cached_df.head(3).iterrows()):
            with top3_cols[idx]:
                st.markdown(f"**{idx + 1}위 · {row['종목명']} ({row['종목코드']})**")
                st.metric("종합점수", f"{float(row['종합점수']):.1f}", delta=f"등급 {row['추천등급']}")
                st.caption(str(row["추천사유"]))


def render_portfolio() -> None:
    user = require_auth()
    inject_pro_css()
    st.title("💼 포트폴리오 트래커")

    _ = add_stock
    user_is_pro = is_pro(user)
    user_is_paid = is_paid(user)
    max_free_stocks = 5

    tracker = PortfolioTracker()
    current_portfolio = get_portfolio()
    portfolio_count = len(current_portfolio) if not current_portfolio.empty else 0

    if not user_is_paid and portfolio_count >= max_free_stocks:
        st.warning(f"🔒 Free 플랜: 포트폴리오 종목 최대 {max_free_stocks}개 (현재 {portfolio_count}개). Plus 업그레이드 시 무제한.")
        can_add = False
    else:
        can_add = True
        if not user_is_paid:
            st.info(f"Free 플랜: 포트폴리오 {portfolio_count}/{max_free_stocks}종목")

    st.subheader("종목 추가")
    with st.form("add_stock_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            add_market = str(st.selectbox("시장", ["KR", "US"]) or "KR")
            add_ticker = st.text_input("종목 코드/티커", placeholder="005930 또는 AAPL")
        with col2:
            add_name = st.text_input("종목명", placeholder="삼성전자")
            add_price = st.number_input("매수 단가", min_value=0.0, step=100.0, format="%.0f")
        with col3:
            add_qty = int(st.number_input("수량", min_value=1, step=1, value=1))
            add_date = st.date_input("매수일")

        submitted = st.form_submit_button("종목 추가", type="primary", use_container_width=True)
        if submitted and add_ticker and add_price > 0:
            if not can_add:
                st.error(f"Free 플랜 종목 한도({max_free_stocks}개)에 도달했습니다. Plus로 업그레이드하세요.")
            else:
                buy_date_value = add_date[0] if isinstance(add_date, tuple) and add_date else add_date
                if buy_date_value is None or isinstance(buy_date_value, tuple):
                    st.error("매수일을 선택하세요.")
                else:
                    tracker.add_holding(
                        ticker=add_ticker,
                        market=add_market,
                        name=add_name,
                        buy_price=add_price,
                        quantity=add_qty,
                        buy_date=str(buy_date_value),
                    )
                    st.success(f"{add_name} ({add_ticker}) 추가 완료!")
                    st.rerun()

    st.markdown("---")
    st.subheader("포트폴리오 현황")

    portfolio_df = get_portfolio()
    if portfolio_df.empty:
        st.info("아직 등록된 종목이 없습니다. 위에서 종목을 추가하세요.")
        _render_portfolio_recommendations(portfolio_df, pd.DataFrame())
        render_fx_crypto_alert_tabs()
        return

    with st.spinner("현재가 조회 중..."):
        holdings = tracker.get_holdings()
    if holdings.empty:
        _render_portfolio_recommendations(portfolio_df, holdings)
        render_fx_crypto_alert_tabs()
        return

    summary = tracker.get_total_value()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("보유 종목 수", f"{summary['종목수']}개")
    col2.metric("총 매수금액", f"{summary['총매수금액']:,.0f}")
    col3.metric("총 평가금액", f"{summary['총평가금액']:,.0f}")
    pnl_delta = f"{summary['총평가손익']:+,.0f}"
    col4.metric("총 평가손익", f"{summary['총평가손익']:,.0f}", pnl_delta)
    col5.metric("총 수익률", f"{summary['총수익률']:.2f}%")

    st.markdown("---")
    render_holdings_table(holdings)

    st.markdown("---")
    _render_portfolio_recommendations(portfolio_df, holdings)

    col_del1, col_del2 = st.columns([3, 1])
    with col_del1:
        delete_id = st.number_input("삭제할 종목 ID", min_value=0, step=1, value=0)
    with col_del2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("종목 삭제", type="secondary") and delete_id > 0:
            remove_stock(int(delete_id))
            st.success(f"ID {delete_id} 종목이 삭제되었습니다.")
            st.rerun()

    st.markdown("---")
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("자산 배분")
        alloc = tracker.get_allocation()
        if not alloc.empty:
            fig_pie = px.pie(alloc, values="평가금액", names="name", title="종목별 비중", hole=0.4)
            fig_pie.update_layout(height=400, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)
    with col_chart2:
        st.subheader("종목별 수익률")
        fig_bar = go.Figure(
            data=[
                go.Bar(
                    x=holdings["name"],
                    y=holdings["수익률(%)"],
                    marker_color=["red" if r >= 0 else "blue" for r in holdings["수익률(%)"]],
                    text=[f"{r:.1f}%" for r in holdings["수익률(%)"]],
                    textposition="auto",
                )
            ]
        )
        fig_bar.update_layout(title="종목별 수익률 (%)", yaxis_title="수익률 (%)", height=400, template="plotly_dark")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")
    render_rebalancing_section(tracker)
    render_pro_analytics(holdings, user_is_pro)
    render_fx_crypto_alert_tabs()
