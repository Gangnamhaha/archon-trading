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

glass_bg = "rgba(26,31,46,0.6)" if is_dark else "rgba(247,248,250,0.7)"
glass_border = "rgba(0,212,170,0.12)"
glass_hover = "rgba(0,212,170,0.4)"
glass_shadow = "rgba(0,212,170,0.15)"

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CUSTOM_CSS = f"""<style>
/* ---- Ticker Bar ---- */
@keyframes ticker-scroll {{
    0%   {{ transform: translateX(0); }}
    100% {{ transform: translateX(-50%); }}
}}
.ticker-wrap {{
    background: #0A0E17;
    overflow: hidden;
    white-space: nowrap;
    padding: 0.35rem 0;
    border-bottom: 1px solid {border};
    margin: -1rem -1rem 1.2rem -1rem;
}}
.ticker-track {{
    display: inline-block;
    animation: ticker-scroll 30s linear infinite;
}}
.ticker-item {{
    display: inline-block;
    padding: 0 1.5rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: {sub_text};
    letter-spacing: 0.02em;
}}
.ticker-item .t-val {{ color: {text}; margin: 0 0.3rem; }}
.ticker-item .t-up  {{ color: #00D4AA; }}
.ticker-item .t-dn  {{ color: #FF4444; }}
.ticker-sep {{ color: {border}; padding: 0 0.5rem; }}

/* ---- Hero ---- */
@keyframes hero-gradient {{
    0%   {{ background-position: 0% 50%; }}
    50%  {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}
@keyframes glow-pulse {{
    0%, 100% {{ text-shadow: 0 0 20px rgba(0,212,170,0.3), 0 0 60px rgba(0,212,170,0.1); }}
    50%      {{ text-shadow: 0 0 30px rgba(0,212,170,0.5), 0 0 80px rgba(0,212,170,0.2); }}
}}
.hero {{
    background: linear-gradient(135deg, #0E1117, #1a1040, #0a2030, #1A1F2E, #0E1117);
    background-size: 400% 400%;
    animation: hero-gradient 8s ease infinite;
    padding: 2.5rem 2rem 2rem;
    border-radius: 16px;
    border: 1px solid {border};
    margin-bottom: 1.5rem;
    text-align: center;
    position: relative;
    overflow: hidden;
}}
.hero::before {{
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 30% 50%, rgba(0,212,170,0.06) 0%, transparent 60%),
                radial-gradient(ellipse at 70% 50%, rgba(100,60,180,0.05) 0%, transparent 60%);
    pointer-events: none;
}}
.hero-title {{
    font-size: 2.8rem;
    font-weight: 800;
    color: {accent};
    margin: 0;
    letter-spacing: 0.15em;
    animation: glow-pulse 3s ease-in-out infinite;
    position: relative;
}}
.hero-sub {{
    color: {sub_text};
    font-size: 1rem;
    margin: 0.4rem 0 0;
    position: relative;
}}
.pro-badge {{
    display: inline-block;
    background: linear-gradient(135deg, {accent}, #00B894);
    color: #0E1117;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
    margin-left: 0.4rem;
    vertical-align: middle;
}}
.hero-stats {{
    display: flex;
    justify-content: center;
    gap: 1rem;
    margin-top: 1.2rem;
    position: relative;
}}
.hero-pill {{
    background: {glass_bg};
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid {glass_border};
    border-radius: 20px;
    padding: 0.35rem 1rem;
    font-size: 0.78rem;
    color: {text};
    font-weight: 600;
}}
.hero-pill span {{ color: {accent}; }}

/* ---- Glassmorphism Cards ---- */
.glass-card {{
    background: {glass_bg};
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid {glass_border};
    border-radius: 12px;
    padding: 1.1rem;
    text-align: center;
    transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s;
}}
.glass-card:hover {{
    border-color: {glass_hover};
    box-shadow: 0 0 24px {glass_shadow};
    transform: translateY(-3px);
}}
.glass-card .idx-name {{ color: {sub_text}; font-size: 0.78rem; margin: 0; }}
.glass-card .idx-val  {{ color: {text}; font-size: 1.35rem; font-weight: 700; margin: 0.25rem 0; }}
.glass-card .idx-chg  {{ font-size: 0.85rem; font-weight: 600; }}
.up   {{ color: #FF4444; }}
.down {{ color: #4488FF; }}
.flat {{ color: {sub_text}; }}

/* ---- Quick Actions ---- */
.qa-card {{
    background: {glass_bg};
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid {glass_border};
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
    transition: border-color 0.3s, box-shadow 0.3s, transform 0.2s;
    cursor: pointer;
}}
.qa-card:hover {{
    border-color: {glass_hover};
    box-shadow: 0 0 20px {glass_shadow};
    transform: translateY(-2px);
}}
.qa-card .qa-icon {{ font-size: 1.6rem; margin-bottom: 0.3rem; }}
.qa-card .qa-label {{ color: {text}; font-size: 0.85rem; font-weight: 600; }}

/* ---- Feature Grid ---- */
.feature-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}}
.feature-item {{
    background: {glass_bg};
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid {glass_border};
    padding: 1.2rem;
    border-radius: 12px;
    transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s;
    position: relative;
    overflow: hidden;
}}
.feature-item::before {{
    content: '';
    position: absolute;
    top: 12px; left: 12px;
    width: 32px; height: 32px;
    background: radial-gradient(circle, rgba(0,212,170,0.15) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}}
.feature-item:hover {{
    border-color: {glass_hover};
    box-shadow: 0 0 20px {glass_shadow};
    transform: translateY(-3px);
}}
.feature-item h4 {{ color: {accent}; margin: 0 0 0.5rem 0; font-size: 0.95rem; }}
.feature-item p  {{ color: {sub_text}; font-size: 0.82rem; margin: 0; line-height: 1.4; }}

/* ---- Sector Heatmap ---- */
.heatmap-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
    margin: 0.8rem 0 1.5rem;
}}
.hm-cell {{
    padding: 0.7rem 0.5rem;
    border-radius: 8px;
    text-align: center;
    font-size: 0.75rem;
    font-weight: 600;
    transition: transform 0.2s;
}}
.hm-cell:hover {{ transform: scale(1.05); }}
.hm-cell .hm-name {{ display: block; margin-bottom: 0.15rem; opacity: 0.9; }}
.hm-cell .hm-pct  {{ display: block; font-size: 0.85rem; }}

/* ---- Section Header ---- */
.section-hdr {{
    color: {text};
    font-size: 1.05rem;
    font-weight: 700;
    margin: 1.5rem 0 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}
.section-hdr .section-note {{
    font-size: 0.7rem;
    color: {sub_text};
    font-weight: 400;
}}

/* ---- Responsive ---- */
@media(max-width:768px){{
    .hero-title {{ font-size: 1.8rem !important; letter-spacing: 0.08em; }}
    .hero {{ padding: 1.5rem 1rem 1.2rem; }}
    .hero-stats {{ flex-wrap: wrap; gap: 0.5rem; }}
    .hero-pill {{ font-size: 0.7rem; padding: 0.25rem 0.7rem; }}
    .feature-grid {{ grid-template-columns: 1fr !important; }}
    .heatmap-grid {{ grid-template-columns: repeat(3, 1fr) !important; }}
    .ticker-item {{ font-size: 0.7rem; padding: 0 1rem; }}
}}
@media(max-width:1024px) and (min-width:769px){{
    .feature-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
}}
@media(max-width:480px){{
    .hero-title {{ font-size: 1.4rem !important; }}
    .hero {{ padding: 1rem 0.8rem; }}
    .feature-grid {{ gap: 0.6rem !important; }}
    .feature-item {{ padding: 0.8rem; }}
    .heatmap-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
}}
</style>"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Market data (unchanged)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# 1. Ticker Bar
# ---------------------------------------------------------------------------
def _render_ticker(data):
    if not data:
        return
    items = []
    for name, d in data.items():
        pct = d["pct"]
        arrow = "&#9650;" if pct > 0 else ("&#9660;" if pct < 0 else "&#8212;")
        cls = "t-up" if pct > 0 else ("t-dn" if pct < 0 else "")
        sign = "+" if pct > 0 else ""
        fmt_v = f"{d['val']:,.2f}" if d["val"] < 10000 else f"{d['val']:,.0f}"
        items.append(
            f'<span class="ticker-item">{name}'
            f'<span class="t-val">{fmt_v}</span>'
            f'<span class="{cls}">{arrow} {sign}{pct:.2f}%</span></span>'
        )
    sep = '<span class="ticker-sep">|</span>'
    row = sep.join(items)
    # duplicate for seamless loop
    st.markdown(
        f'<div class="ticker-wrap"><div class="ticker-track">{row}{sep}{row}</div></div>',
        unsafe_allow_html=True,
    )

_render_ticker(market_data)

# ---------------------------------------------------------------------------
# 2. Hero Section
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="hero">
    <h1 class="hero-title">ARCHON</h1>
    <p class="hero-sub">
        AI-Powered Trading Terminal
        <span class="pro-badge">PRO</span>
    </p>
    <div class="hero-stats">
        <div class="hero-pill"><span>12</span> Modules</div>
        <div class="hero-pill"><span>5</span> AI Models</div>
        <div class="hero-pill"><span>3</span> Brokers</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 3. Market Summary — Glassmorphism Cards
# ---------------------------------------------------------------------------
st.markdown('<div class="section-hdr">Market Overview</div>', unsafe_allow_html=True)

if market_data:
    cols = st.columns(len(market_data))
    for col, (name, data) in zip(cols, market_data.items()):
        pct = data["pct"]
        cls = "up" if pct > 0 else ("down" if pct < 0 else "flat")
        sign = "+" if pct > 0 else ""
        arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
        fmt_val = f"{data['val']:,.2f}" if data["val"] < 10000 else f"{data['val']:,.0f}"
        col.markdown(f"""
        <div class="glass-card">
            <p class="idx-name">{name}</p>
            <p class="idx-val">{fmt_val}</p>
            <p class="idx-chg {cls}">{arrow} {sign}{data['chg']:,.2f} ({sign}{pct:.2f}%)</p>
        </div>
        """, unsafe_allow_html=True)
else:
    st.caption("시장 데이터 로딩 중...")

# ---------------------------------------------------------------------------
# 4. Quick Actions
# ---------------------------------------------------------------------------
st.markdown('<div class="section-hdr">Quick Access</div>', unsafe_allow_html=True)
qa_cols = st.columns(4)
qa_items = [
    ("pages/1_데이터분석.py", "📊", "데이터분석"),
    ("pages/6_AI예측.py", "🤖", "AI예측"),
    ("pages/11_종목추천.py", "🏆", "종목추천"),
    ("pages/5_자동매매.py", "⚡", "자동매매"),
]
for col, (page, icon, label) in zip(qa_cols, qa_items):
    col.markdown(f"""
    <div class="qa-card">
        <div class="qa-icon">{icon}</div>
        <div class="qa-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)
    col.page_link(page, label=f"{icon} {label} 바로가기", use_container_width=True)

# ---------------------------------------------------------------------------
# 5. Feature Grid — Glassmorphism
# ---------------------------------------------------------------------------
st.markdown('<div class="section-hdr">Features</div>', unsafe_allow_html=True)
st.markdown("""
<div class="feature-grid">
    <div class="feature-item">
        <h4>📈 Data Analysis</h4>
        <p>Real-time price data, candlestick charts, multi-stock comparison for KR &amp; US markets</p>
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

# ---------------------------------------------------------------------------
# 6. Sector Heatmap
# ---------------------------------------------------------------------------
SECTORS = [
    ("IT", 1.82), ("금융", -0.45), ("헬스케어", 2.14), ("에너지", -1.33),
    ("소비재", 0.67), ("산업", -0.21), ("소재", 1.05), ("통신", -0.78),
    ("유틸리티", 0.32), ("부동산", -1.60), ("반도체", 2.95), ("자동차", -0.53),
]


def _hm_color(pct):
    """Map percentage to color between red(-3%) and green(+3%)."""
    t = max(-3.0, min(3.0, pct)) / 3.0  # -1 to 1
    if t >= 0:
        r = int(45 - 45 * t)
        g = int(55 + (212 - 55) * t)
        b = int(72 - 72 * t + 170 * t)
    else:
        at = abs(t)
        r = int(45 + (255 - 45) * at)
        g = int(55 + (68 - 55) * at)
        b = int(72 - 4 * at)
    return f"rgb({r},{g},{b})"


st.markdown(
    '<div class="section-hdr">Sector Overview '
    '<span class="section-note">(샘플 데이터)</span></div>',
    unsafe_allow_html=True,
)

cells = []
for name, pct in SECTORS:
    color = _hm_color(pct)
    sign = "+" if pct > 0 else ""
    txt_color = "#FFFFFF" if abs(pct) > 1.0 else text
    cells.append(
        f'<div class="hm-cell" style="background:{color};color:{txt_color};">'
        f'<span class="hm-name">{name}</span>'
        f'<span class="hm-pct">{sign}{pct:.2f}%</span></div>'
    )
st.markdown(
    '<div class="heatmap-grid">' + "".join(cells) + '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar (unchanged)
# ---------------------------------------------------------------------------
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
