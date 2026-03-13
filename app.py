import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from config.auth import require_auth, logout, is_pro
from data.database import get_watchlist, add_watchlist, remove_watchlist

st.set_page_config(
    page_title="Archon - Trading Terminal",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

user = require_auth()
_user_is_pro = is_pro(user)

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

/* ---- Greeting + Portfolio Summary ---- */
.greeting {{ color: {text}; font-size: 1.15rem; font-weight: 600; margin: 0; }}
.greeting-time {{ color: {sub_text}; font-size: 0.82rem; }}
.ps-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.8rem; margin: 0.8rem 0 0; }}
.ps-card {{
    background: {glass_bg}; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid {glass_border}; border-radius: 10px; padding: 0.8rem; text-align: center;
}}
.ps-card .ps-label {{ color: {sub_text}; font-size: 0.72rem; margin: 0; }}
.ps-card .ps-val {{ color: {text}; font-size: 1.15rem; font-weight: 700; margin: 0.15rem 0; }}
.ps-card .ps-sub {{ font-size: 0.75rem; font-weight: 600; }}

/* ---- Market Status ---- */
.mkt-status {{
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: {glass_bg}; backdrop-filter: blur(8px);
    border: 1px solid {glass_border}; border-radius: 20px;
    padding: 0.2rem 0.7rem; font-size: 0.72rem; font-weight: 600; color: {sub_text};
}}
.mkt-dot {{
    width: 7px; height: 7px; border-radius: 50%; display: inline-block;
}}
.mkt-dot.open {{ background: #00D4AA; box-shadow: 0 0 6px #00D4AA; }}
.mkt-dot.pre  {{ background: #FFC107; box-shadow: 0 0 6px #FFC107; }}
.mkt-dot.closed {{ background: #FF4444; }}

/* ---- Fear & Greed Gauge ---- */
.fg-wrap {{
    background: {glass_bg}; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid {glass_border}; border-radius: 12px; padding: 1rem; text-align: center;
}}
.fg-label {{ color: {sub_text}; font-size: 0.75rem; margin: 0; }}
.fg-value {{ font-size: 1.5rem; font-weight: 800; margin: 0.2rem 0; }}
.fg-desc {{ color: {sub_text}; font-size: 0.8rem; font-weight: 600; }}

/* ---- Top Movers ---- */
.movers-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 0.8rem 0; }}
.movers-col {{ background: {glass_bg}; backdrop-filter: blur(12px); border: 1px solid {glass_border}; border-radius: 12px; padding: 1rem; }}
.movers-col h4 {{ color: {text}; font-size: 0.9rem; margin: 0 0 0.6rem; }}
.mover-row {{ display: flex; justify-content: space-between; align-items: center; padding: 0.35rem 0; border-bottom: 1px solid rgba(45,55,72,0.4); }}
.mover-row:last-child {{ border-bottom: none; }}
.mover-rank {{ color: {sub_text}; font-size: 0.7rem; width: 18px; }}
.mover-name {{ color: {text}; font-size: 0.82rem; font-weight: 600; flex: 1; margin: 0 0.4rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.mover-pct {{ font-size: 0.82rem; font-weight: 700; min-width: 55px; text-align: right; }}

/* ---- News Preview ---- */
.news-list {{ margin: 0.6rem 0; }}
.news-row {{
    display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem 0.8rem;
    background: {glass_bg}; border: 1px solid {glass_border}; border-radius: 8px; margin-bottom: 0.4rem;
    transition: border-color 0.2s;
}}
.news-row:hover {{ border-color: {glass_hover}; }}
.news-badge {{ font-size: 0.65rem; font-weight: 700; padding: 0.1rem 0.4rem; border-radius: 4px; white-space: nowrap; }}
.news-badge.pos {{ background: rgba(0,212,170,0.15); color: #00D4AA; }}
.news-badge.neg {{ background: rgba(255,68,68,0.15); color: #FF4444; }}
.news-badge.neu {{ background: rgba(160,174,192,0.15); color: {sub_text}; }}
.news-title {{ color: {text}; font-size: 0.82rem; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.news-src {{ color: {sub_text}; font-size: 0.68rem; white-space: nowrap; }}

/* ---- Pro Lock Badge ---- */
.qa-lock {{ position: relative; }}
.qa-lock::after {{
    content: "PRO";
    position: absolute; top: 6px; right: 6px;
    background: linear-gradient(135deg, {accent}, #00B894);
    color: #0E1117; font-size: 0.55rem; font-weight: 800;
    padding: 0.1rem 0.35rem; border-radius: 3px;
}}

/* ---- Sparkline ---- */
.spark-row {{ display: flex; align-items: center; gap: 0.4rem; }}
.spark-row .spark-info {{ flex: 1; }}
.spark-row svg {{ flex-shrink: 0; }}

/* ---- Responsive ---- */
@media(max-width:768px){{
    .hero-title {{ font-size: 1.8rem !important; letter-spacing: 0.08em; }}
    .hero {{ padding: 1.5rem 1rem 1.2rem; }}
    .hero-stats {{ flex-wrap: wrap; gap: 0.5rem; }}
    .hero-pill {{ font-size: 0.7rem; padding: 0.25rem 0.7rem; }}
    .feature-grid {{ grid-template-columns: 1fr !important; }}
    .heatmap-grid {{ grid-template-columns: repeat(3, 1fr) !important; }}
    .ticker-item {{ font-size: 0.7rem; padding: 0 1rem; }}
    .ps-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
    .movers-grid {{ grid-template-columns: 1fr !important; }}
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


@st.cache_data(ttl=300)
def _fetch_top_movers():
    from pykrx import stock as krx
    from datetime import datetime, timedelta
    today = datetime.now()
    for offset in range(7):
        date_str = (today - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            df = krx.get_market_ohlcv_by_ticker(date_str, market="KOSPI")
            if df.empty:
                continue
            gainers, losers = [], []
            for ticker_code in df.nlargest(5, "등락률").index:
                try:
                    nm = krx.get_market_ticker_name(ticker_code)
                except Exception:
                    nm = ticker_code
                r = df.loc[ticker_code]
                gainers.append({"name": nm, "price": int(r["종가"]), "pct": float(r["등락률"])})
            for ticker_code in df.nsmallest(5, "등락률").index:
                try:
                    nm = krx.get_market_ticker_name(ticker_code)
                except Exception:
                    nm = ticker_code
                r = df.loc[ticker_code]
                losers.append({"name": nm, "price": int(r["종가"]), "pct": float(r["등락률"])})
            return {"gainers": gainers, "losers": losers}
        except Exception:
            continue
    return None


@st.cache_data(ttl=600)
def _fetch_vix():
    import yfinance as yf
    try:
        hist = yf.Ticker("^VIX").history(period="5d")
        if len(hist) >= 1:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def _fetch_sector_real():
    from pykrx import stock as krx
    from datetime import datetime, timedelta
    CODES = [
        ("IT", "1028"), ("금융", "1024"), ("건설", "1020"), ("의약품", "1011"),
        ("운수장비", "1017"), ("전기전자", "1015"), ("유통", "1018"),
        ("철강금속", "1013"), ("화학", "1010"), ("기계", "1014"),
        ("통신", "1022"), ("서비스", "1026"),
    ]
    today = datetime.now()
    for offset in range(7):
        d = (today - timedelta(days=offset)).strftime("%Y%m%d")
        p = (today - timedelta(days=offset + 1)).strftime("%Y%m%d")
        results = []
        for name, code in CODES:
            try:
                cur = krx.get_index_ohlcv(d, d, code)
                prev = krx.get_index_ohlcv(p, p, code)
                if not cur.empty and not prev.empty:
                    pct = float((cur["종가"].iloc[-1] / prev["종가"].iloc[-1] - 1) * 100)
                    results.append((name, pct))
            except Exception:
                continue
        if len(results) >= 6:
            return results
    return None


@st.cache_data(ttl=600)
def _fetch_news_headlines():
    try:
        from data.news import fetch_and_analyze, NEWS_SOURCES
        sources = list(NEWS_SOURCES.keys())[:3]
        df = fetch_and_analyze(sources, None)
        if df is not None and not df.empty:
            return df.head(5).to_dict("records")
    except Exception:
        pass
    return None


def _get_market_status():
    from datetime import datetime
    try:
        import pytz
        kst = pytz.timezone("Asia/Seoul")
        est = pytz.timezone("US/Eastern")
        now_kst = datetime.now(kst)
        now_est = datetime.now(est)
    except ImportError:
        now_kst = datetime.now()
        now_est = now_kst
    kr_wd = now_kst.weekday()
    kr_h, kr_m = now_kst.hour, now_kst.minute
    kr_mins = kr_h * 60 + kr_m
    if kr_wd < 5 and 540 <= kr_mins <= 930:
        kr_status, kr_cls = "장중", "open"
    else:
        kr_status, kr_cls = "장마감", "closed"
    us_wd = now_est.weekday()
    us_h, us_m = now_est.hour, now_est.minute
    us_mins = us_h * 60 + us_m
    if us_wd < 5 and 570 <= us_mins <= 960:
        us_status, us_cls = "장중", "open"
    elif us_wd < 5 and 240 <= us_mins < 570:
        us_status, us_cls = "프리마켓", "pre"
    elif us_wd < 5 and 960 < us_mins <= 1200:
        us_status, us_cls = "애프터마켓", "pre"
    else:
        us_status, us_cls = "장마감", "closed"
    return {"kr": (kr_status, kr_cls), "us": (us_status, us_cls)}


def _portfolio_summary():
    try:
        from data.database import get_portfolio
        pf = get_portfolio()
        if pf.empty:
            return None
        count = len(pf)
        total_cost = float((pf["buy_price"] * pf["quantity"]).sum()) if "buy_price" in pf.columns and "quantity" in pf.columns else 0
        return {"count": count, "total_cost": total_cost}
    except Exception:
        return None


def _make_sparkline(values, width=60, height=20, color="#00D4AA"):
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    points = []
    for i, v in enumerate(values):
        x = i / (len(values) - 1) * width
        y = height - ((v - mn) / rng) * height
        points.append(f"{x:.1f},{y:.1f}")
    end_color = "#00D4AA" if values[-1] >= values[0] else "#FF4444"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{" ".join(points)}" fill="none" stroke="{end_color}" stroke-width="1.5" stroke-linecap="round"/>'
        f'</svg>'
    )


top_movers = _fetch_top_movers()
vix_val = _fetch_vix()
news_headlines = _fetch_news_headlines()
mkt_status = _get_market_status()
pf_summary = _portfolio_summary()

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
kr_st, kr_cl = mkt_status["kr"]
us_st, us_cl = mkt_status["us"]
st.markdown(f"""
<div class="hero">
    <div style="display:flex;justify-content:center;gap:0.6rem;margin-bottom:0.6rem;">
        <span class="mkt-status"><span class="mkt-dot {kr_cl}"></span>KRX {kr_st}</span>
        <span class="mkt-status"><span class="mkt-dot {us_cl}"></span>US {us_st}</span>
    </div>
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
# 2.5  Greeting + Portfolio Summary
# ---------------------------------------------------------------------------
from datetime import datetime as _dt
_hour = _dt.now().hour
_greet = "좋은 아침이에요" if _hour < 12 else ("좋은 오후에요" if _hour < 18 else "좋은 저녁이에요")

_ps_cards = ""
if pf_summary:
    _ps_cards += f'<div class="ps-card"><p class="ps-label">보유 종목</p><p class="ps-val">{pf_summary["count"]}</p></div>'
    _ps_cards += f'<div class="ps-card"><p class="ps-label">총 투자금</p><p class="ps-val">{pf_summary["total_cost"]:,.0f}</p><p class="ps-sub" style="color:{sub_text}">원</p></div>'
else:
    _ps_cards += f'<div class="ps-card"><p class="ps-label">보유 종목</p><p class="ps-val">0</p></div>'
    _ps_cards += f'<div class="ps-card"><p class="ps-label">총 투자금</p><p class="ps-val">—</p></div>'

_wl_cnt = len(get_watchlist(user["username"])) if not get_watchlist(user["username"]).empty else 0
_ps_cards += f'<div class="ps-card"><p class="ps-label">워치리스트</p><p class="ps-val">{_wl_cnt}</p></div>'
_plan_label = '<span style="color:#00D4AA">💎 Pro</span>' if _user_is_pro else '<span style="color:#A0AEC0">🆓 Free</span>'
_ps_cards += f'<div class="ps-card"><p class="ps-label">플랜</p><p class="ps-val">{_plan_label}</p></div>'

st.markdown(f"""
<p class="greeting">{_greet}, <span style="color:{accent}">{user['username']}</span>님</p>
<p class="greeting-time">{_dt.now().strftime('%Y년 %m월 %d일 %A')}</p>
<div class="ps-grid">{_ps_cards}</div>
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
# 3.5  Fear & Greed Gauge (VIX-based)
# ---------------------------------------------------------------------------
if vix_val is not None:
    if vix_val < 12:
        fg_label, fg_color = "극단적 탐욕", "#00D4AA"
    elif vix_val < 17:
        fg_label, fg_color = "탐욕", "#4AEDC4"
    elif vix_val < 25:
        fg_label, fg_color = "중립", "#FFC107"
    elif vix_val < 30:
        fg_label, fg_color = "공포", "#FF8C00"
    else:
        fg_label, fg_color = "극단적 공포", "#FF4444"

    import math as _math
    fg_angle = max(0, min(180, (vix_val / 40) * 180))
    _fg_rad = _math.radians(180 - fg_angle)
    _fg_cx = 10 + 160 * (fg_angle / 180)
    _fg_cy = 90 - 80 * _math.sin(_fg_rad)
    _fg_offset = 251 - (fg_angle / 180) * 251
    fg_col1, fg_col2, fg_col3 = st.columns([1, 2, 1])
    with fg_col2:
        st.markdown(f"""
        <div class="fg-wrap">
            <p class="fg-label">Fear & Greed Index (VIX 기반)</p>
            <svg width="180" height="100" viewBox="0 0 180 100" style="margin:0.3rem auto;display:block">
                <path d="M 10 90 A 80 80 0 0 1 170 90" fill="none" stroke="#2D3748" stroke-width="12" stroke-linecap="round"/>
                <path d="M 10 90 A 80 80 0 0 1 170 90" fill="none"
                      stroke="url(#fgGrad)" stroke-width="12" stroke-linecap="round"
                      stroke-dasharray="251" stroke-dashoffset="{_fg_offset:.1f}"/>
                <defs><linearGradient id="fgGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#00D4AA"/><stop offset="50%" stop-color="#FFC107"/><stop offset="100%" stop-color="#FF4444"/>
                </linearGradient></defs>
                <circle cx="{_fg_cx:.1f}" cy="{_fg_cy:.1f}" r="5" fill="{fg_color}"/>
            </svg>
            <p class="fg-value" style="color:{fg_color}">{vix_val:.1f}</p>
            <p class="fg-desc" style="color:{fg_color}">{fg_label}</p>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 4. Quick Actions
# ---------------------------------------------------------------------------
st.markdown('<div class="section-hdr">Quick Access</div>', unsafe_allow_html=True)
qa_cols = st.columns(4)
qa_items = [
    ("pages/1_데이터분석.py", "📊", "데이터분석", False),
    ("pages/6_AI예측.py", "🤖", "AI예측", True),
    ("pages/10_종목추천.py", "🏆", "종목추천", True),
    ("pages/5_자동매매.py", "⚡", "자동매매", True),
]
for col, (page, icon, label, pro_only) in zip(qa_cols, qa_items):
    lock_cls = ' qa-lock' if pro_only and not _user_is_pro else ''
    col.markdown(f"""
    <div class="qa-card{lock_cls}">
        <div class="qa-icon">{icon}</div>
        <div class="qa-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)
    col.page_link(page, label=f"{icon} {label} 바로가기", use_container_width=True)

# ---------------------------------------------------------------------------
# 4.5  Top Movers (KOSPI)
# ---------------------------------------------------------------------------
if top_movers:
    st.markdown('<div class="section-hdr">KOSPI 급등/급락 TOP 5</div>', unsafe_allow_html=True)
    g_rows = ""
    for i, g in enumerate(top_movers["gainers"], 1):
        g_rows += (
            f'<div class="mover-row"><span class="mover-rank">{i}</span>'
            f'<span class="mover-name">{g["name"]}</span>'
            f'<span class="mover-pct up">+{g["pct"]:.2f}%</span></div>'
        )
    l_rows = ""
    for i, l in enumerate(top_movers["losers"], 1):
        l_rows += (
            f'<div class="mover-row"><span class="mover-rank">{i}</span>'
            f'<span class="mover-name">{l["name"]}</span>'
            f'<span class="mover-pct down">{l["pct"]:.2f}%</span></div>'
        )
    st.markdown(f"""
    <div class="movers-grid">
        <div class="movers-col"><h4>🔺 급등</h4>{g_rows}</div>
        <div class="movers-col"><h4>🔻 급락</h4>{l_rows}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 4.7  News Headlines
# ---------------------------------------------------------------------------
if news_headlines:
    st.markdown('<div class="section-hdr">오늘의 뉴스</div>', unsafe_allow_html=True)
    n_rows = ""
    for n in news_headlines:
        sent = n.get("감성", "중립")
        if "긍정" in sent:
            badge_cls, badge_txt = "pos", "긍정"
        elif "부정" in sent:
            badge_cls, badge_txt = "neg", "부정"
        else:
            badge_cls, badge_txt = "neu", "중립"
        title = n.get("제목", "")[:60]
        src = n.get("출처", "")
        n_rows += (
            f'<div class="news-row">'
            f'<span class="news-badge {badge_cls}">{badge_txt}</span>'
            f'<span class="news-title">{title}</span>'
            f'<span class="news-src">{src}</span>'
            f'</div>'
        )
    st.markdown(f'<div class="news-list">{n_rows}</div>', unsafe_allow_html=True)

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
_real_sectors = _fetch_sector_real()
SECTORS = _real_sectors if _real_sectors else [
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


_sector_note = "" if _real_sectors else ' <span class="section-note">(샘플 데이터)</span>'
st.markdown(
    f'<div class="section-hdr">Sector Overview{_sector_note}</div>',
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
_plan_badge = "💎 Pro" if _user_is_pro else "🆓 Free"
st.sidebar.markdown(f"**{user['username']}** ({user['role']}) — {_plan_badge}")

theme_label = "☀️ Light" if is_dark else "🌙 Dark"
if st.sidebar.button(theme_label, use_container_width=True):
    st.session_state["theme"] = "light" if is_dark else "dark"
    st.rerun()

if st.sidebar.button("Logout", use_container_width=True):
    logout()
st.sidebar.markdown("---")

st.sidebar.markdown("### ⭐ 워치리스트")

_MAX_FREE_WATCHLIST = 3
wl = get_watchlist(user["username"])
_wl_count = len(wl) if not wl.empty else 0
_wl_can_add = _user_is_pro or _wl_count < _MAX_FREE_WATCHLIST

if not _user_is_pro:
    st.sidebar.caption(f"🔒 Free: {_wl_count}/{_MAX_FREE_WATCHLIST}종목")

with st.sidebar.expander("종목 추가", expanded=False):
    wl_ticker = st.text_input("종목코드", key="wl_add_ticker", placeholder="005930")
    wl_name = st.text_input("종목명", key="wl_add_name", placeholder="삼성전자")
    wl_market = st.selectbox("시장", ["KR", "US"], key="wl_add_market")
    if st.button("추가", key="wl_add_btn", use_container_width=True):
        if not _wl_can_add:
            st.error(f"Free 플랜 한도({_MAX_FREE_WATCHLIST}종목)에 도달했습니다.")
        elif wl_ticker and wl_name:
            add_watchlist(wl_ticker, wl_market, wl_name, user["username"])
            st.rerun()

if not wl.empty:
    @st.cache_data(ttl=600)
    def _wl_sparkline(ticker_code, market_code):
        import yfinance as yf
        try:
            sym = ticker_code if market_code == "US" else f"{ticker_code}.KS"
            hist = yf.Ticker(sym).history(period="7d")
            if len(hist) >= 2:
                return hist["Close"].tolist()
        except Exception:
            pass
        return []

    for _, row in wl.iterrows():
        c1, c2, c3 = st.sidebar.columns([3, 2, 1])
        spark_vals = _wl_sparkline(row["ticker"], row["market"])
        spark_svg = _make_sparkline(spark_vals) if spark_vals else ""
        c1.markdown(f"**{row['name']}** `{row['ticker']}`")
        if spark_svg:
            c2.markdown(spark_svg, unsafe_allow_html=True)
        if c3.button("✕", key=f"wl_rm_{row['ticker']}"):
            remove_watchlist(row["ticker"], user["username"])
            st.rerun()
else:
    st.sidebar.caption("워치리스트가 비어있습니다.")

st.sidebar.markdown("---")
st.sidebar.info("KR: KRX (KOSPI/KOSDAQ)\n\nUS: NYSE / NASDAQ")
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Archon** v2.0 | Python 3.9+")
