from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from data.fetcher import fetch_stock


def _fetch_stock_safe(ticker: str, market_code: str, period: str, interval: str) -> pd.DataFrame:
    try:
        return fetch_stock(ticker, market_code, period, interval)
    except TypeError:
        return fetch_stock(ticker, market_code, period)


def render_price_and_compare(ticker: str, market_code: str, period: str, interval: str) -> None:
    if not str(ticker).strip():
        st.warning("종목 코드를 입력하세요.")
        return
    with st.spinner(f"{ticker} 데이터 로딩 중..."):
        df = _fetch_stock_safe(ticker, market_code, period, interval)
    if df.empty:
        st.error(f"'{ticker}' 데이터를 가져올 수 없습니다.")
        return
    required_cols = {"Open", "High", "Low", "Close", "Volume"}
    if not required_cols.issubset(set(df.columns.astype(str).tolist())):
        st.error("차트에 필요한 OHLCV 컬럼이 누락되었습니다.")
        return

    latest = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2]) if len(df) > 1 else latest
    change = latest - prev
    change_pct = change / prev * 100 if prev else 0
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("현재가", f"{latest:,.0f}", f"{change:+,.0f} ({change_pct:+.2f}%)")
    c2.metric("최고가", f"{df['High'].max():,.0f}")
    c3.metric("최저가", f"{df['Low'].min():,.0f}")
    c4.metric("평균 거래량", f"{df['Volume'].mean():,.0f}")
    c5.metric("기간 수익률", f"{(df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100:.2f}%")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], subplot_titles=["가격", "거래량"])
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="가격"), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=["red" if c >= o else "blue" for c, o in zip(df["Close"], df["Open"])]), row=2, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    st.subheader("다중 종목 수익률 비교")
    compare_market = str(st.selectbox("비교 시장", ["US (미국)", "KR (한국)"], key="compare_market") or "US (미국)")
    compare_code = compare_market.split(" ")[0]
    defaults = "AAPL, MSFT, GOOGL, NVDA" if compare_code == "US" else "005930, 000660, 035720, 051910"
    if st.session_state.get("_prev_compare_market") != compare_code:
        st.session_state["compare_tickers_input"] = defaults
        st.session_state["_prev_compare_market"] = compare_code

    tickers = st.text_input("비교할 종목", value=defaults, key="compare_tickers_input")
    compare_period = st.selectbox("비교 기간", ["1mo", "3mo", "6mo", "1y"], index=2, key="compare_period")
    if st.button("수익률 비교", use_container_width=True, key="compare_returns"):
        fig2 = go.Figure()
        added = 0
        for t in [x.strip() for x in tickers.split(",") if x.strip()]:
            normalized = t.upper() if compare_code == "US" else t
            data = fetch_stock(normalized, compare_code, compare_period)
            if not data.empty:
                fig2.add_trace(go.Scatter(x=data.index, y=(data["Close"] / data["Close"].iloc[0] - 1) * 100, name=normalized, mode="lines"))
                added += 1
        if added == 0:
            st.warning("비교 가능한 종목 데이터가 없어 차트를 생성하지 못했습니다. 티커/시장/기간을 확인하세요.")
        else:
            fig2.update_layout(template="plotly_dark", height=500, title="종목별 수익률 비교 (%)", hovermode="x unified")
            st.plotly_chart(fig2, use_container_width=True)


@st.cache_data(ttl=300)
def fetch_crypto_market_table() -> pd.DataFrame:
    mapping = {"BTC-USD": "비트코인", "ETH-USD": "이더리움", "BNB-USD": "바이낸스코인", "SOL-USD": "솔라나", "XRP-USD": "리플"}
    rows: list[dict[str, Any]] = []
    for ticker, name in mapping.items():
        hist = yf.Ticker(ticker).history(period="7d")
        if hist.empty or "Close" not in hist.columns:
            continue
        curr = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr
        rows.append({"코인": name, "티커": ticker.replace("-USD", ""), "현재가(USD)": round(curr, 2), "24h(%)": round((curr / prev - 1) * 100, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def fetch_economic_indicators() -> pd.DataFrame:
    metrics = {"^TNX": ("미국 10년 국채금리", "%"), "DX-Y.NYB": ("달러 인덱스", ""), "USDKRW=X": ("USD/KRW 환율", "원"), "GC=F": ("금 (Gold)", "USD/oz")}
    rows: list[dict[str, Any]] = []
    for ticker, (name, unit) in metrics.items():
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty or "Close" not in hist.columns:
            continue
        curr = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr
        rows.append({"지표": name, "현재값": f"{curr:,.2f} {unit}", "전일비(%)": round((curr / prev - 1) * 100, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def fetch_global_indices() -> pd.DataFrame:
    indices = {"^GSPC": "S&P 500", "^DJI": "다우존스", "^IXIC": "나스닥", "^KS11": "KOSPI"}
    rows: list[dict[str, Any]] = []
    for ticker, name in indices.items():
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty or "Close" not in hist.columns:
            continue
        curr = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr
        rows.append({"지수": name, "현재": f"{curr:,.2f}", "전일비(%)": round((curr / prev - 1) * 100, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def fetch_investor_trend() -> pd.DataFrame:
    try:
        from pykrx import stock as krx

        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        df = krx.get_market_trading_value_by_date(start, today, "KOSPI")
        if df.empty:
            return pd.DataFrame()
        data = df.reset_index()
        data.columns = ["날짜"] + list(data.columns[1:])
        return data.tail(20)
    except Exception:
        return pd.DataFrame()
