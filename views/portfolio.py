# pyright: basic
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
        render_fx_crypto_alert_tabs()
        return

    with st.spinner("현재가 조회 중..."):
        holdings = tracker.get_holdings()
    if holdings.empty:
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
