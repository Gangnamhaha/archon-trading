import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
from config.styles import inject_pro_css, show_legal_disclaimer
from config.auth import require_auth, is_pro

st.set_page_config(page_title="글로벌 마켓", page_icon="🌍", layout="wide")
user = require_auth()
inject_pro_css()
st.title("🌍 글로벌 마켓 & 경제지표")

tab1, tab2, tab3, tab4 = st.tabs(["암호화폐", "경제지표", "글로벌 지수", "투자자 동향"])

with tab1:
    st.subheader("₿ 암호화폐 시장")

    @st.cache_data(ttl=300)
    def _fetch_crypto():
        cryptos = {"BTC-USD": "비트코인", "ETH-USD": "이더리움", "BNB-USD": "바이낸스코인",
                    "SOL-USD": "솔라나", "XRP-USD": "리플", "ADA-USD": "카르다노",
                    "DOGE-USD": "도지코인", "DOT-USD": "폴카닷"}
        rows = []
        for ticker, name in cryptos.items():
            try:
                t = yf.Ticker(ticker)
                h = t.history(period="7d")
                if h.empty:
                    continue
                curr = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) >= 2 else curr
                chg = (curr / prev - 1) * 100
                w_start = float(h["Close"].iloc[0])
                w_chg = (curr / w_start - 1) * 100
                vol = float(h["Volume"].iloc[-1])
                rows.append({"코인": name, "티커": ticker.replace("-USD",""),
                             "현재가(USD)": round(curr, 2), "24h(%)": round(chg, 2),
                             "7일(%)": round(w_chg, 2), "거래량": f"{vol:,.0f}"})
            except Exception:
                continue
        return pd.DataFrame(rows)

    if st.button("암호화폐 데이터 로드", type="primary", use_container_width=True, key="load_crypto"):
        with st.spinner("암호화폐 데이터 로딩..."):
            crypto_df = _fetch_crypto()
            if crypto_df.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                def _color_pct(val):
                    try:
                        v = float(val)
                        return "color:#FF4444" if v < 0 else "color:#00D4AA"
                    except (ValueError, TypeError):
                        return ""
                styled = crypto_df.style.applymap(_color_pct, subset=["24h(%)", "7일(%)"])
                st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")
    _crypto_ticker = st.selectbox("차트 보기", ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD"], key="crypto_chart_sel")
    _crypto_period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], key="crypto_period")
    if st.button("차트 로드", use_container_width=True, key="load_crypto_chart"):
        with st.spinner("차트 로딩..."):
            t = yf.Ticker(_crypto_ticker)
            h = t.history(period=_crypto_period)
            if not h.empty:
                fig = go.Figure(data=[go.Candlestick(x=h.index, open=h["Open"], high=h["High"], low=h["Low"], close=h["Close"])])
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  title=f"{_crypto_ticker} 캔들차트", height=450, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("📈 주요 경제지표")

    @st.cache_data(ttl=600)
    def _fetch_economic():
        indicators = {
            "^TNX": ("미국 10년 국채금리", "%"),
            "^IRX": ("미국 3개월 국채금리", "%"),
            "DX-Y.NYB": ("달러 인덱스", ""),
            "USDKRW=X": ("USD/KRW 환율", "원"),
            "USDJPY=X": ("USD/JPY 환율", "엔"),
            "EURUSD=X": ("EUR/USD 환율", ""),
            "GC=F": ("금 (Gold)", "USD/oz"),
            "CL=F": ("WTI 원유", "USD/bbl"),
            "SI=F": ("은 (Silver)", "USD/oz"),
        }
        rows = []
        for ticker, (name, unit) in indicators.items():
            try:
                t = yf.Ticker(ticker)
                h = t.history(period="5d")
                if h.empty:
                    continue
                curr = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) >= 2 else curr
                chg = round((curr / prev - 1) * 100, 2)
                rows.append({"지표": name, "현재값": f"{curr:,.2f} {unit}", "전일비(%)": chg})
            except Exception:
                continue
        return pd.DataFrame(rows)

    if st.button("경제지표 로드", type="primary", use_container_width=True, key="load_econ"):
        with st.spinner("경제지표 로딩..."):
            econ_df = _fetch_economic()
            if econ_df.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                cols = st.columns(3)
                for i, (_, row) in enumerate(econ_df.iterrows()):
                    with cols[i % 3]:
                        delta = f"{row['전일비(%)']:+.2f}%"
                        st.metric(row["지표"], row["현재값"], delta)

with tab3:
    st.subheader("🌐 글로벌 주요 지수")

    @st.cache_data(ttl=300)
    def _fetch_global_indices():
        indices = {
            "^GSPC": "S&P 500", "^DJI": "다우존스", "^IXIC": "나스닥",
            "^N225": "닛케이225", "^HSI": "항셍", "000001.SS": "상해종합",
            "^FTSE": "FTSE 100", "^GDAXI": "DAX", "^KS11": "KOSPI",
        }
        rows = []
        for ticker, name in indices.items():
            try:
                t = yf.Ticker(ticker)
                h = t.history(period="5d")
                if h.empty:
                    continue
                curr = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) >= 2 else curr
                chg = round((curr / prev - 1) * 100, 2)
                rows.append({"지수": name, "현재": f"{curr:,.2f}", "전일비(%)": chg})
            except Exception:
                continue
        return pd.DataFrame(rows)

    if st.button("글로벌 지수 로드", type="primary", use_container_width=True, key="load_global"):
        with st.spinner("글로벌 지수 로딩..."):
            gdf = _fetch_global_indices()
            if gdf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                cols = st.columns(3)
                for i, (_, row) in enumerate(gdf.iterrows()):
                    with cols[i % 3]:
                        delta = f"{row['전일비(%)']:+.2f}%"
                        st.metric(row["지수"], row["현재"], delta)

with tab4:
    st.subheader("🏦 투자자 동향 (KRX)")

    @st.cache_data(ttl=600)
    def _fetch_investor_trend():
        try:
            from pykrx import stock as krx
            today = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
            df = krx.get_market_trading_value_by_date(start, today, "KOSPI")
            if df.empty:
                return pd.DataFrame()
            df = df.reset_index()
            df.columns = ["날짜"] + list(df.columns[1:])
            return df.tail(20)
        except Exception:
            return pd.DataFrame()

    if st.button("투자자 동향 로드", type="primary", use_container_width=True, key="load_investor"):
        with st.spinner("투자자 동향 로딩..."):
            inv_df = _fetch_investor_trend()
            if inv_df.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                st.dataframe(inv_df, use_container_width=True, hide_index=True)

                numeric_cols = [c for c in inv_df.columns if c != "날짜"]
                if len(numeric_cols) >= 3:
                    fig = go.Figure()
                    colors = ["#00D4AA", "#FF6B6B", "#4ECDC4", "#FFE66D"]
                    for i, col in enumerate(numeric_cols[:4]):
                        fig.add_trace(go.Bar(name=col, x=inv_df["날짜"].astype(str), y=inv_df[col],
                                             marker_color=colors[i % len(colors)]))
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                      plot_bgcolor="rgba(0,0,0,0)", title="투자자별 순매매 추이",
                                      barmode="group", height=400)
                    st.plotly_chart(fig, use_container_width=True)

show_legal_disclaimer()
