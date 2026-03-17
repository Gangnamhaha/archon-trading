import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from config.auth import require_auth, logout, is_paid, is_pro
from config.styles import inject_pro_css
from data.database import get_watchlist, add_watchlist, remove_watchlist

st.set_page_config(
    page_title="Archon - Trading Terminal",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

user = require_auth()
inject_pro_css(show_logout=False)
_user_is_pro = is_pro(user)
_user_is_paid = is_paid(user)
_user_plan = "pro" if _user_is_pro else ("plus" if str(user.get("plan", "free")) == "plus" else "free")

# ---------------------------------------------------------------------------
# Market data
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

    for sym, label in [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ")]:
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
# Main Content
# ---------------------------------------------------------------------------

# Greeting + Plan Badge
_plan_emoji = "💎" if _user_plan == "pro" else ("✨" if _user_plan == "plus" else "🆓")
st.markdown(f"### Welcome, **{user['username']}** ({_plan_emoji} {_user_plan.upper()})")

# 3-Step Guide
st.markdown("#### 오늘 시작 가이드")
step_cols = st.columns(3)
step_cols[0].page_link("pages/1_데이터분석.py", label="1) 데이터 확인", icon="📊", use_container_width=True)
step_cols[1].page_link("pages/5_종목추천.py", label="2) 종목 추천 받기", icon="🏆", use_container_width=True)
step_cols[2].page_link("pages/10_자동매매.py", label="3) 자동매매 실행", icon="⚡", use_container_width=True)

# Market Indices (4 metrics)
st.markdown("#### Market Overview")
if market_data:
    idx_cols = st.columns(4)
    indices = ["KOSPI", "KOSDAQ", "S&P 500", "NASDAQ"]
    for col, idx_name in zip(idx_cols, indices):
        if idx_name in market_data:
            d = market_data[idx_name]
            delta = f"{d['chg']:+.2f} ({d['pct']:+.2f}%)"
            col.metric(idx_name, f"{d['val']:,.0f}", delta)
        else:
            col.metric(idx_name, "—", "—")
else:
    st.caption("시장 데이터 로딩 중...")

# Quick Access (4 buttons)
st.markdown("#### Quick Access")
qa_cols = st.columns(4)
if _user_is_pro:
    qa_items = [
        ("pages/10_자동매매.py", "⚡ 자동매매"),
        ("pages/5_종목추천.py", "🏆 종목추천"),
        ("pages/6_AI예측.py", "🤖 AI예측"),
        ("pages/13_마케팅도구.py", "📣 마케팅도구"),
    ]
elif _user_is_paid:
    qa_items = [
        ("pages/1_데이터분석.py", "📊 데이터분석"),
        ("pages/7_백테스팅.py", "🧪 백테스팅"),
        ("pages/12_뉴스감성분석.py", "📰 뉴스감성분석"),
        ("pages/9_포트폴리오.py", "📁 포트폴리오"),
    ]
else:
    qa_items = [
        ("pages/1_데이터분석.py", "📊 데이터분석"),
        ("pages/18_자주하는질문.py", "❓ 자주하는질문"),
        ("pages/17_고객문의.py", "📩 고객문의"),
        ("pages/14_결제.py", "💳 플랜 업그레이드"),
    ]
for col, (page, label) in zip(qa_cols, qa_items):
    col.page_link(page, label=label, use_container_width=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
if _user_plan == "pro":
    _plan_badge = "💎 Pro"
elif _user_plan == "plus":
    _plan_badge = "✨ Plus"
else:
    _plan_badge = "🆓 Free"
st.sidebar.markdown(f"**{user['username']}** ({user['role']}) — {_plan_badge}")

st.sidebar.markdown("---")

st.sidebar.markdown("### ⭐ 워치리스트")

_MAX_FREE_WATCHLIST = 3
wl = get_watchlist(user["username"])
_wl_count = len(wl) if not wl.empty else 0
_wl_can_add = _user_is_paid or _wl_count < _MAX_FREE_WATCHLIST

if not _user_is_paid:
    st.sidebar.caption(f"🔒 Free: {_wl_count}/{_MAX_FREE_WATCHLIST}종목")

with st.sidebar.expander("종목 추가", expanded=False):
    wl_ticker = st.text_input("종목코드", key="wl_add_ticker", placeholder="005930")
    wl_name = st.text_input("종목명", key="wl_add_name", placeholder="삼성전자")
    wl_market = str(st.selectbox("시장", ["KR", "US"], key="wl_add_market") or "KR")
    if st.button("추가", key="wl_add_btn", use_container_width=True):
        if not _wl_can_add:
            st.error(f"Free 플랜 한도({_MAX_FREE_WATCHLIST}종목)에 도달했습니다.")
        elif wl_ticker and wl_name:
            add_watchlist(wl_ticker, wl_market, wl_name, user["username"])
            st.rerun()

if not wl.empty:
    for _, row in wl.iterrows():
        c1, c2 = st.sidebar.columns([4, 1])
        c1.markdown(f"**{row['name']}** `{row['ticker']}`")
        if c2.button("✕", key=f"wl_rm_{row['ticker']}"):
            remove_watchlist(str(row["ticker"]), user["username"])
            st.rerun()
else:
    st.sidebar.caption("워치리스트가 비어있습니다.")

st.sidebar.markdown("---")
st.sidebar.info("KR: KRX (KOSPI/KOSDAQ)\n\nUS: NYSE / NASDAQ")
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Archon** v2.0 | Python 3.9+")
if st.sidebar.button("Logout", key="home_logout", use_container_width=True):
    logout()
