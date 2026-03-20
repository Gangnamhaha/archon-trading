from datetime import datetime, timedelta
from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from analysis.technical import calc_all_indicators, get_signal_summary
from config.auth import is_paid
from config.styles import show_legal_disclaimer
from data.fetcher import fetch_stock, get_us_popular_stocks


def render_charts(user: dict[str, Any]) -> None:
    _ = user
    section = st.radio("하위 섹션", ["📈 데이터분석", "🌍 글로벌마켓", "📊 기술적분석"], horizontal=True)
    if section == "📈 데이터분석":
        _render_data_analysis()
    elif section == "🌍 글로벌마켓":
        _render_global_market()
    else:
        _render_technical_analysis()


def _render_data_analysis() -> None:
    st.subheader("📈 주가 데이터 분석")
    user_is_paid = is_paid()
    market = str(st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"], key="data_market") or "US (미국)")
    market_code = market.split(" ")[0]
    if market_code == "US":
        popular = get_us_popular_stocks()
        selected = st.sidebar.selectbox("인기 종목", popular["ticker"].tolist(), index=0, key="data_popular")
        if selected and st.session_state.get("_prev_data_popular") != selected:
            st.session_state["data_ticker_input"] = selected
            st.session_state["_prev_data_popular"] = selected
        ticker = st.sidebar.text_input("종목 티커", key="data_ticker_input")
    else:
        ticker = st.sidebar.text_input("종목 코드", key="data_ticker_code")
    period = st.sidebar.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3, key="data_period")
    if user_is_paid:
        interval = st.sidebar.selectbox("차트 간격", ["1d", "1wk", "1mo", "5m", "15m", "1h"], key="data_interval")
    else:
        interval = "1d"
        st.sidebar.info("🔒 차트 간격: 일봉만 (Plus 업그레이드 시 분봉/주봉 가능)")
    if st.sidebar.button("조회", type="primary", use_container_width=True, key="data_fetch"):
        st.session_state.update({"data_ticker": ticker, "data_market": market_code, "data_period": period, "data_interval": interval})
    if "data_ticker" in st.session_state:
        _show_price_and_compare(st.session_state["data_ticker"], st.session_state["data_market"], st.session_state["data_period"])


def _show_price_and_compare(ticker: str, market_code: str, period: str) -> None:
    with st.spinner(f"{ticker} 데이터 로딩 중..."):
        df = fetch_stock(ticker, market_code, period)
    if df.empty:
        st.error(f"'{ticker}' 데이터를 가져올 수 없습니다.")
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
    tickers = st.text_input("비교할 종목", value=defaults, key="compare_tickers_input")
    compare_period = st.selectbox("비교 기간", ["1mo", "3mo", "6mo", "1y"], index=2, key="compare_period")
    if st.button("수익률 비교", use_container_width=True, key="compare_returns"):
        fig2 = go.Figure()
        for t in [x.strip() for x in tickers.split(",") if x.strip()]:
            d = fetch_stock(t, compare_code, compare_period)
            if not d.empty:
                fig2.add_trace(go.Scatter(x=d.index, y=(d["Close"] / d["Close"].iloc[0] - 1) * 100, name=t, mode="lines"))
        fig2.update_layout(template="plotly_dark", height=500, title="종목별 수익률 비교 (%)", hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)


def _render_global_market() -> None:
    st.subheader("🌍 글로벌 마켓 & 경제지표")
    tab1, tab2, tab3, tab4 = st.tabs(["암호화폐", "경제지표", "글로벌 지수", "투자자 동향"])

    with tab1:
        if st.button("암호화폐 데이터 로드", type="primary", use_container_width=True, key="load_crypto"):
            cdf = _fetch_crypto()
            st.dataframe(cdf, use_container_width=True, hide_index=True) if not cdf.empty else st.error("데이터를 가져올 수 없습니다.")
        coin = st.selectbox("차트 보기", ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD"], key="crypto_chart_sel")
        cperiod = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], key="crypto_period")
        if st.button("차트 로드", use_container_width=True, key="load_crypto_chart"):
            hist = yf.Ticker(coin).history(period=cperiod)
            if not hist.empty:
                fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"])])
                fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, title=f"{coin} 캔들차트")
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if st.button("경제지표 로드", type="primary", use_container_width=True, key="load_econ"):
            edf = _fetch_economic()
            if edf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                cols = st.columns(3)
                for i, (_, row) in enumerate(edf.iterrows()):
                    cols[i % 3].metric(cast(Any, row["지표"]), cast(Any, row["현재값"]), f"{row['전일비(%)']:+.2f}%")

    with tab3:
        if st.button("글로벌 지수 로드", type="primary", use_container_width=True, key="load_global"):
            gdf = _fetch_indices()
            if gdf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                cols = st.columns(3)
                for i, (_, row) in enumerate(gdf.iterrows()):
                    cols[i % 3].metric(cast(Any, row["지수"]), cast(Any, row["현재"]), f"{row['전일비(%)']:+.2f}%")

    with tab4:
        if st.button("투자자 동향 로드", type="primary", use_container_width=True, key="load_investor"):
            idf = _fetch_investor_trend()
            if idf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                st.dataframe(idf, use_container_width=True, hide_index=True)
    show_legal_disclaimer()


@st.cache_data(ttl=300)
def _fetch_crypto() -> pd.DataFrame:
    mapping = {"BTC-USD": "비트코인", "ETH-USD": "이더리움", "BNB-USD": "바이낸스코인", "SOL-USD": "솔라나", "XRP-USD": "리플"}
    rows: list[dict[str, Any]] = []
    for ticker, name in mapping.items():
        hist = yf.Ticker(ticker).history(period="7d")
        if hist.empty:
            continue
        curr = float(hist["Close"].iloc[-1]); prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr
        rows.append({"코인": name, "티커": ticker.replace("-USD", ""), "현재가(USD)": round(curr, 2), "24h(%)": round((curr / prev - 1) * 100, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def _fetch_economic() -> pd.DataFrame:
    metrics = {"^TNX": ("미국 10년 국채금리", "%"), "DX-Y.NYB": ("달러 인덱스", ""), "USDKRW=X": ("USD/KRW 환율", "원"), "GC=F": ("금 (Gold)", "USD/oz")}
    rows: list[dict[str, Any]] = []
    for ticker, (name, unit) in metrics.items():
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            continue
        curr = float(hist["Close"].iloc[-1]); prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr
        rows.append({"지표": name, "현재값": f"{curr:,.2f} {unit}", "전일비(%)": round((curr / prev - 1) * 100, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def _fetch_indices() -> pd.DataFrame:
    indices = {"^GSPC": "S&P 500", "^DJI": "다우존스", "^IXIC": "나스닥", "^KS11": "KOSPI"}
    rows: list[dict[str, Any]] = []
    for ticker, name in indices.items():
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            continue
        curr = float(hist["Close"].iloc[-1]); prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else curr
        rows.append({"지수": name, "현재": f"{curr:,.2f}", "전일비(%)": round((curr / prev - 1) * 100, 2)})
    return pd.DataFrame(rows)


@st.cache_data(ttl=600)
def _fetch_investor_trend() -> pd.DataFrame:
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


def _render_technical_analysis() -> None:
    st.subheader("📊 기술적 분석")
    user_is_paid = is_paid()
    max_free = 5
    market = str(st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"], key="ta_market") or "US (미국)")
    market_code = market.split(" ")[0]
    ticker = st.sidebar.text_input("종목 티커" if market_code == "US" else "종목 코드", value="AAPL" if market_code == "US" else "005930", key="ta_ticker")
    period = st.sidebar.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y"], index=2, key="ta_period")
    show_sma = st.sidebar.checkbox("이동평균선 (SMA)", value=True, key="ta_show_sma")
    sma_periods = st.sidebar.multiselect("SMA 기간", [5, 10, 20, 60, 120], default=[5, 20, 60], key="ta_sma_periods")
    show_bb = st.sidebar.checkbox("볼린저밴드", value=True, key="ta_show_bb")
    show_rsi = st.sidebar.checkbox("RSI", value=True, key="ta_show_rsi")
    show_macd = st.sidebar.checkbox("MACD", value=True, key="ta_show_macd")
    if not user_is_paid:
        selected = [f"SMA{p}" for p in sma_periods] if show_sma else []
        if show_bb:
            selected.append("BB")
        if show_rsi:
            selected.append("RSI")
        if show_macd:
            selected.append("MACD")
        if len(selected) > max_free:
            st.sidebar.warning(f"⚠️ Free 플랜: 지표 최대 {max_free}개")
            show_macd = show_macd and "MACD" not in selected[max_free:]
            show_rsi = show_rsi and "RSI" not in selected[max_free:]
            show_bb = show_bb and "BB" not in selected[max_free:]
            sma_periods = [p for p in sma_periods if f"SMA{p}" not in selected[max_free:]]
    if st.sidebar.button("분석 실행", type="primary", use_container_width=True, key="ta_run"):
        st.session_state.update({"ta_ticker": ticker, "ta_market": market_code, "ta_period": period})
    if "ta_ticker" not in st.session_state:
        st.info("왼쪽 사이드바에서 종목을 입력하고 '분석 실행' 버튼을 클릭하세요.")
        return

    df = fetch_stock(st.session_state["ta_ticker"], st.session_state["ta_market"], st.session_state["ta_period"])
    if df.empty:
        st.error("데이터를 가져올 수 없습니다.")
        return
    ta = calc_all_indicators(df)
    signal = get_signal_summary(ta)
    st.write(f"종합 시그널: **{signal['signal']}**")
    with st.expander("현재 지표 수치"):
        latest = ta.iloc[-1]
        st.json({k: round(float(v), 4) for k, v in latest.items() if k not in ["Open", "High", "Low", "Close", "Volume"] and pd.notna(v)})
