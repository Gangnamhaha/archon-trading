import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from config.auth import require_auth, logout

st.set_page_config(
    page_title="Archon - Trading Terminal",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

user = require_auth()

if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

is_dark = st.session_state["theme"] == "dark"
bg = "#0E1117" if is_dark else "#FFFFFF"
card_bg = "#1A1F2E" if is_dark else "#F7F8FA"
border = "#2D3748" if is_dark else "#E2E8F0"
text = "#E2E8F0" if is_dark else "#1A202C"
sub_text = "#A0AEC0" if is_dark else "#718096"
accent = "#00D4AA"

CUSTOM_CSS = f"""<style>
    .main-header {{
        background: linear-gradient(135deg, {bg} 0%, {card_bg} 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border: 1px solid {border};
        margin-bottom: 1.5rem;
    }}
    .feature-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1.5rem 0;
    }}
    .feature-item {{
        background: {card_bg};
        padding: 1.2rem;
        border-radius: 10px;
        border: 1px solid {border};
        transition: border-color 0.3s;
    }}
    .feature-item:hover {{ border-color: {accent}; }}
    .feature-item h4 {{ color: {accent}; margin: 0 0 0.5rem 0; }}
    .feature-item p {{ color: {sub_text}; font-size: 0.85rem; margin: 0; }}
    .pro-badge {{
        display: inline-block;
        background: linear-gradient(135deg, {accent}, #00B894);
        color: #0E1117;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
        margin-left: 0.5rem;
    }}
    .market-card {{
        background: {card_bg};
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid {border};
        text-align: center;
    }}
    .market-card .idx-name {{ color: {sub_text}; font-size: 0.8rem; margin: 0; }}
    .market-card .idx-val {{ color: {text}; font-size: 1.3rem; font-weight: 700; margin: 0.2rem 0; }}
    .market-card .idx-chg {{ font-size: 0.85rem; font-weight: 600; }}
    .up {{ color: #FF4444; }}
    .down {{ color: #4488FF; }}
    .flat {{ color: {sub_text}; }}
    .watchlist-item {{
        background: {card_bg};
        padding: 0.6rem 1rem;
        border-radius: 8px;
        border: 1px solid {border};
        margin-bottom: 0.3rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .watchlist-item .wl-name {{ color: {text}; font-weight: 600; }}
    .watchlist-item .wl-ticker {{ color: {sub_text}; font-size: 0.8rem; }}

    @media(max-width:768px){{
        .main .block-container{{padding:0.5rem 0.8rem !important}}
        [data-testid="stHorizontalBlock"]{{flex-wrap:wrap !important;gap:0.3rem !important}}
        [data-testid="stHorizontalBlock"]>div{{flex:1 1 100% !important;min-width:100% !important}}
        .feature-grid{{grid-template-columns:1fr !important}}
        .main-header h1{{font-size:1.3rem !important}}
        .main-header p{{font-size:0.85rem !important}}
        .feature-item h4{{font-size:0.95rem}}
        .feature-item p{{font-size:0.8rem}}
    }}
    @media(max-width:1024px) and (min-width:769px){{
        .feature-grid{{grid-template-columns:repeat(2,1fr) !important}}
    }}
    @media(max-width:480px){{
        .main .block-container{{padding:0.3rem 0.5rem !important}}
        .feature-grid{{grid-template-columns:1fr !important;gap:0.6rem !important}}
        .feature-item{{padding:0.8rem}}
        .main-header{{padding:1rem}}
        .main-header h1{{font-size:1.1rem !important}}
    }}
</style>"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(f"""
<div class="main-header">
    <h1 style="color: {accent}; margin: 0;">Archon Trading Terminal</h1>
    <p style="color: {sub_text}; margin: 0.3rem 0 0 0;">
        AI 주식자동매매플랫폼
        <span class="pro-badge">PRO</span>
    </p>
</div>
""", unsafe_allow_html=True)

st.subheader("📊 시장 현황")


@st.cache_data(ttl=300)
def _fetch_market_summary():
    from pykrx import stock as krx
    from datetime import datetime, timedelta
    import yfinance as yf

    results = {}
    today = datetime.now()

    for offset in range(7):
        date_str = (today - timedelta(days=offset)).strftime("%Y%m%d")
        prev_str = (today - timedelta(days=offset + 1)).strftime("%Y%m%d")
        try:
            kospi = krx.get_index_ohlcv(date_str, date_str, "1001")
            kosdaq = krx.get_index_ohlcv(date_str, date_str, "2001")
            if not kospi.empty and not kosdaq.empty:
                kospi_prev = krx.get_index_ohlcv(prev_str, prev_str, "1001")
                kosdaq_prev = krx.get_index_ohlcv(prev_str, prev_str, "2001")
                results["KOSPI"] = {
                    "val": float(kospi["종가"].iloc[-1]),
                    "chg": float(kospi["종가"].iloc[-1] - kospi_prev["종가"].iloc[-1]) if not kospi_prev.empty else 0,
                    "pct": float((kospi["종가"].iloc[-1] / kospi_prev["종가"].iloc[-1] - 1) * 100) if not kospi_prev.empty else 0,
                }
                results["KOSDAQ"] = {
                    "val": float(kosdaq["종가"].iloc[-1]),
                    "chg": float(kosdaq["종가"].iloc[-1] - kosdaq_prev["종가"].iloc[-1]) if not kosdaq_prev.empty else 0,
                    "pct": float((kosdaq["종가"].iloc[-1] / kosdaq_prev["종가"].iloc[-1] - 1) * 100) if not kosdaq_prev.empty else 0,
                }
                break
        except Exception:
            continue

    for sym, label in [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ"), ("^DJI", "DOW")]:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if len(hist) >= 2:
                cur = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                results[label] = {
                    "val": cur,
                    "chg": cur - prev,
                    "pct": (cur / prev - 1) * 100,
                }
        except Exception:
            continue

    return results


market_data = _fetch_market_summary()

if market_data:
    cols = st.columns(len(market_data))
    for col, (name, data) in zip(cols, market_data.items()):
        pct = data["pct"]
        cls = "up" if pct > 0 else ("down" if pct < 0 else "flat")
        sign = "+" if pct > 0 else ""
        fmt_val = f"{data['val']:,.2f}" if data["val"] < 10000 else f"{data['val']:,.0f}"
        col.markdown(f"""
        <div class="market-card">
            <p class="idx-name">{name}</p>
            <p class="idx-val">{fmt_val}</p>
            <p class="idx-chg {cls}">{sign}{data['chg']:,.2f} ({sign}{pct:.2f}%)</p>
        </div>
        """, unsafe_allow_html=True)
else:
    st.caption("시장 데이터 로딩 중...")

st.markdown("---")

st.markdown("""
<div class="feature-grid">
    <div class="feature-item">
        <h4>📈 Data Analysis</h4>
        <p>Real-time price data, candlestick charts, multi-stock comparison for KR & US markets</p>
    </div>
    <div class="feature-item">
        <h4>📉 Technical Analysis</h4>
        <p>15+ indicators: SMA, RSI, MACD, Bollinger, Ichimoku, ATR, OBV, ADX, CCI, Williams %R</p>
    </div>
    <div class="feature-item">
        <h4>🔄 Backtesting Engine</h4>
        <p>Strategy testing with equity curves, Sharpe ratio, MDD, win rate analysis</p>
    </div>
    <div class="feature-item">
        <h4>🤖 AI Prediction</h4>
        <p>Ensemble forecasting: Holt-Winters, ARIMA, ML Regression with confidence intervals</p>
    </div>
    <div class="feature-item">
        <h4>⚠️ Risk Analytics</h4>
        <p>VaR, CVaR, Sortino, Beta/Alpha, Efficient Frontier portfolio optimization</p>
    </div>
    <div class="feature-item">
        <h4>🏆 Stock Recommend</h4>
        <p>Multi-factor scoring: technical + momentum + volume + trend consistency</p>
    </div>
    <div class="feature-item">
        <h4>🔍 Stock Screener</h4>
        <p>Multi-condition filtering, preset strategies, RSI/MACD/volume-based screening</p>
    </div>
    <div class="feature-item">
        <h4>📰 News Sentiment</h4>
        <p>RSS news aggregation, keyword-based sentiment analysis, market mood tracking</p>
    </div>
    <div class="feature-item">
        <h4>⚡ Auto Trading Bot</h4>
        <p>KIS/Kiwoom API, strategy-based orders, scheduler, real-time signal monitoring</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"**{user['username']}** ({user['role']})")

theme_label = "☀️ Light" if is_dark else "🌙 Dark"
if st.sidebar.button(theme_label, use_container_width=True):
    st.session_state["theme"] = "light" if is_dark else "dark"
    st.rerun()

if st.sidebar.button("Logout", use_container_width=True):
    logout()
st.sidebar.markdown("---")

st.sidebar.markdown("### ⭐ 워치리스트")
from data.database import get_watchlist, add_watchlist, remove_watchlist

wl = get_watchlist(user["username"])

with st.sidebar.expander("종목 추가", expanded=False):
    wl_ticker = st.text_input("종목코드", key="wl_add_ticker", placeholder="005930")
    wl_name = st.text_input("종목명", key="wl_add_name", placeholder="삼성전자")
    wl_market = st.selectbox("시장", ["KR", "US"], key="wl_add_market")
    if st.button("추가", key="wl_add_btn", use_container_width=True):
        if wl_ticker and wl_name:
            add_watchlist(wl_ticker, wl_market, wl_name, user["username"])
            st.rerun()

if not wl.empty:
    for _, row in wl.iterrows():
        c1, c2 = st.sidebar.columns([4, 1])
        c1.markdown(f"**{row['name']}** `{row['ticker']}`")
        if c2.button("✕", key=f"wl_rm_{row['ticker']}"):
            remove_watchlist(row["ticker"], user["username"])
            st.rerun()
else:
    st.sidebar.caption("워치리스트가 비어있습니다.")

st.sidebar.markdown("---")
st.sidebar.info("KR: KRX (KOSPI/KOSDAQ)\n\nUS: NYSE / NASDAQ")
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Archon** v2.0 | Python 3.9+")
