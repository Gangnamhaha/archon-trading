"""
데이터 분석 페이지
- 한국/미국 주가 데이터 조회
- 캔들스틱 차트, 거래량, 수익률 비교
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data.fetcher import fetch_stock, get_us_popular_stocks
from config.styles import inject_pro_css
from config.auth import require_auth

st.set_page_config(page_title="데이터 분석", page_icon="📈", layout="wide")
require_auth()
inject_pro_css()
st.title("📈 주가 데이터 분석")

# === 사이드바 설정 ===
st.sidebar.header("설정")
market = st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"])
market_code = market.split(" ")[0]

# 종목 입력
if market_code == "US":
    popular = get_us_popular_stocks()
    ticker_options = popular["ticker"].tolist()
    selected = st.sidebar.selectbox("인기 종목", ticker_options, index=0)
    ticker = st.sidebar.text_input("종목 티커", value=selected, help="직접 입력 가능 (예: AAPL)")
else:
    ticker = st.sidebar.text_input("종목 코드", value="005930", help="6자리 종목코드 (예: 005930 = 삼성전자)")

period = st.sidebar.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)

# === 데이터 조회 ===
if st.sidebar.button("조회", type="primary", use_container_width=True):
    st.session_state["data_ticker"] = ticker
    st.session_state["data_market"] = market_code
    st.session_state["data_period"] = period

if "data_ticker" in st.session_state:
    ticker = st.session_state["data_ticker"]
    market_code = st.session_state["data_market"]
    period = st.session_state["data_period"]

    with st.spinner(f"{ticker} 데이터 로딩 중..."):
        df = fetch_stock(ticker, market_code, period)

    if df.empty:
        st.error(f"'{ticker}' 데이터를 가져올 수 없습니다. 종목 코드를 확인하세요.")
    else:
        # 기본 정보
        col1, col2, col3, col4, col5 = st.columns(5)
        latest = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2] if len(df) > 1 else latest
        change = latest - prev
        change_pct = (change / prev * 100) if prev != 0 else 0

        col1.metric("현재가", f"{latest:,.0f}", f"{change:+,.0f} ({change_pct:+.2f}%)")
        col2.metric("최고가", f"{df['High'].max():,.0f}")
        col3.metric("최저가", f"{df['Low'].min():,.0f}")
        col4.metric("평균 거래량", f"{df['Volume'].mean():,.0f}")
        col5.metric("기간 수익률", f"{(df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100:.2f}%")

        st.markdown("---")

        # 캔들스틱 차트 + 거래량
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=["가격 차트", "거래량"]
        )

        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="가격"
            ), row=1, col=1
        )

        colors = ["red" if c >= o else "blue" for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(
            go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=colors, opacity=0.5),
            row=2, col=1
        )

        fig.update_layout(
            height=700,
            xaxis_rangeslider_visible=False,
            showlegend=False,
            title=f"{ticker} 주가 차트",
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

        # 일별 수익률 분포
        st.subheader("일별 수익률 분포")
        daily_returns = df["Close"].pct_change().dropna() * 100
        fig2 = go.Figure(data=[go.Histogram(x=daily_returns, nbinsx=50, name="일별 수익률 (%)")])
        fig2.update_layout(
            xaxis_title="수익률 (%)", yaxis_title="빈도",
            height=400, template="plotly_dark",
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 데이터 테이블
        with st.expander("원본 데이터 보기"):
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

# === 다중 종목 비교 ===
st.markdown("---")
st.subheader("다중 종목 수익률 비교")

compare_market = st.selectbox("비교 시장", ["US (미국)", "KR (한국)"], key="compare_market")
compare_market_code = compare_market.split(" ")[0]

if compare_market_code == "US":
    default_tickers = "AAPL, MSFT, GOOGL, NVDA"
else:
    default_tickers = "005930, 000660, 035720, 051910"

tickers_input = st.text_input(
    "비교할 종목 (쉼표로 구분)",
    value=default_tickers,
    help="예: AAPL, MSFT, GOOGL"
)
compare_period = st.selectbox("비교 기간", ["1mo", "3mo", "6mo", "1y"], index=2, key="compare_period")

if st.button("수익률 비교", use_container_width=True):
    tickers = [t.strip() for t in tickers_input.split(",") if t.strip()]
    fig3 = go.Figure()

    for t in tickers:
        with st.spinner(f"{t} 로딩..."):
            data = fetch_stock(t, compare_market_code, compare_period)
        if not data.empty:
            normalized = (data["Close"] / data["Close"].iloc[0] - 1) * 100
            fig3.add_trace(go.Scatter(x=data.index, y=normalized, name=t, mode="lines"))

    fig3.update_layout(
        title="종목별 수익률 비교 (%)",
        xaxis_title="날짜", yaxis_title="수익률 (%)",
        height=500, hovermode="x unified",
        template="plotly_dark",
    )
    st.plotly_chart(fig3, use_container_width=True)
