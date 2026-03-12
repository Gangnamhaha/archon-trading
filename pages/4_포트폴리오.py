"""
포트폴리오 페이지
- 보유 종목 관리
- 수익률 추적, 자산 배분 분석
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from data.database import add_stock, remove_stock, get_portfolio
from data.fetcher import fetch_stock
from portfolio.tracker import PortfolioTracker
from config.styles import inject_pro_css

st.set_page_config(page_title="포트폴리오", page_icon="💼", layout="wide")
inject_pro_css()
st.title("💼 포트폴리오 트래커")

tracker = PortfolioTracker()

# === 종목 추가 폼 ===
st.subheader("종목 추가")
with st.form("add_stock_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        add_market = st.selectbox("시장", ["KR", "US"])
        add_ticker = st.text_input("종목 코드/티커", placeholder="005930 또는 AAPL")
    with col2:
        add_name = st.text_input("종목명", placeholder="삼성전자")
        add_price = st.number_input("매수 단가", min_value=0.0, step=100.0, format="%.0f")
    with col3:
        add_qty = st.number_input("수량", min_value=1, step=1, value=1)
        add_date = st.date_input("매수일")

    submitted = st.form_submit_button("종목 추가", type="primary", use_container_width=True)
    if submitted and add_ticker and add_price > 0:
        tracker.add_holding(
            ticker=add_ticker, market=add_market, name=add_name,
            buy_price=add_price, quantity=add_qty,
            buy_date=add_date.strftime("%Y-%m-%d")
        )
        st.success(f"{add_name} ({add_ticker}) 추가 완료!")
        st.rerun()

st.markdown("---")

# === 포트폴리오 요약 ===
st.subheader("포트폴리오 현황")

portfolio_df = get_portfolio()
if portfolio_df.empty:
    st.info("아직 등록된 종목이 없습니다. 위에서 종목을 추가하세요.")
else:
    # 현재가 조회 및 수익률 계산
    with st.spinner("현재가 조회 중..."):
        holdings = tracker.get_holdings()

    if not holdings.empty:
        # 요약 지표
        summary = tracker.get_total_value()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("보유 종목 수", f"{summary['종목수']}개")
        col2.metric("총 매수금액", f"{summary['총매수금액']:,.0f}")
        col3.metric("총 평가금액", f"{summary['총평가금액']:,.0f}")
        pnl_delta = f"{summary['총평가손익']:+,.0f}"
        col4.metric("총 평가손익", f"{summary['총평가손익']:,.0f}", pnl_delta)
        ret_color = "normal" if summary["총수익률"] >= 0 else "inverse"
        col5.metric("총 수익률", f"{summary['총수익률']:.2f}%")

        st.markdown("---")

        # 보유 종목 테이블
        st.subheader("보유 종목 상세")
        display_df = holdings[["id", "name", "ticker", "market", "buy_price", "quantity",
                                "현재가", "매수금액", "평가금액", "평가손익", "수익률(%)"]].copy()
        display_df.columns = ["ID", "종목명", "코드", "시장", "매수단가", "수량",
                              "현재가", "매수금액", "평가금액", "평가손익", "수익률(%)"]

        # 수익률에 따른 색상 표시
        st.dataframe(
            display_df.style.applymap(
                lambda v: "color: red" if isinstance(v, (int, float)) and v > 0 else (
                    "color: blue" if isinstance(v, (int, float)) and v < 0 else ""
                ),
                subset=["평가손익", "수익률(%)"]
            ),
            use_container_width=True,
            hide_index=True
        )

        # 종목 삭제
        col_del1, col_del2 = st.columns([3, 1])
        with col_del1:
            delete_id = st.number_input("삭제할 종목 ID", min_value=0, step=1, value=0)
        with col_del2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("종목 삭제", type="secondary"):
                if delete_id > 0:
                    remove_stock(delete_id)
                    st.success(f"ID {delete_id} 종목이 삭제되었습니다.")
                    st.rerun()

        st.markdown("---")

        # 자산 배분 파이차트
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("자산 배분")
            alloc = tracker.get_allocation()
            if not alloc.empty:
                fig_pie = px.pie(
                    alloc, values="평가금액", names="name",
                    title="종목별 비중",
                    hole=0.4
                )
                fig_pie.update_layout(height=400, template="plotly_dark")
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_chart2:
            st.subheader("종목별 수익률")
            fig_bar = go.Figure(data=[
                go.Bar(
                    x=holdings["name"],
                    y=holdings["수익률(%)"],
                    marker_color=["red" if r >= 0 else "blue" for r in holdings["수익률(%)"]],
                    text=[f"{r:.1f}%" for r in holdings["수익률(%)"]],
                    textposition="auto"
                )
            ])
            fig_bar.update_layout(
                title="종목별 수익률 (%)",
                yaxis_title="수익률 (%)",
                height=400, template="plotly_dark",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
