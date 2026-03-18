import streamlit as st

from config.auth import is_paid, is_pro, logout, require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences
from data.database import add_watchlist, get_recent_activity, get_watchlist, log_user_activity, remove_watchlist


@st.cache_data(ttl=300)
def _fetch_market_summary():
    from datetime import datetime, timedelta

    import yfinance as yf
    from pykrx import stock as krx

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
                    "pct": float((kospi["종가"].iloc[-1] / kospi_prev["종가"].iloc[-1] - 1) * 100)
                    if not kospi_prev.empty
                    else 0,
                }
                results["KOSDAQ"] = {
                    "val": float(kosdaq["종가"].iloc[-1]),
                    "chg": float(kosdaq["종가"].iloc[-1] - kosdaq_prev["종가"].iloc[-1]) if not kosdaq_prev.empty else 0,
                    "pct": float((kosdaq["종가"].iloc[-1] / kosdaq_prev["종가"].iloc[-1] - 1) * 100)
                    if not kosdaq_prev.empty
                    else 0,
                }
                break
        except Exception:
            continue

    for sym, label in [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ")]:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
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


def render_home():
    user = require_auth()
    username = str(user["username"])
    visit_key = f"_visit_logged_home_{username}"
    if not st.session_state.get(visit_key):
        log_user_activity(username, "page_visit", "", "홈")
        st.session_state[visit_key] = True

    saved_home = load_user_preferences(username, "home")
    default_indices = ["KOSPI", "KOSDAQ", "S&P 500", "NASDAQ"]
    saved_indices = saved_home.get("indices_order", default_indices)
    if not isinstance(saved_indices, list):
        saved_indices = default_indices
    normalized_saved = [idx for idx in saved_indices if idx in default_indices] + [
        idx for idx in default_indices if idx not in saved_indices
    ]
    st.session_state.setdefault("home_indices_order", normalized_saved)
    st.session_state.setdefault("_home_pref_last", tuple(st.session_state["home_indices_order"]))

    inject_pro_css(show_logout=False)
    user_is_pro = is_pro(user)
    user_is_paid = is_paid(user)
    user_plan = "pro" if user_is_pro else ("plus" if str(user.get("plan", "free")) == "plus" else "free")

    market_data = _fetch_market_summary()

    plan_emoji = "💎" if user_plan == "pro" else ("✨" if user_plan == "plus" else "🆓")
    st.markdown(f"### Welcome, **{user['username']}** ({plan_emoji} {user_plan.upper()})")

    st.markdown("#### 오늘 시작 가이드")
    step_cols = st.columns(3)
    if step_cols[0].button("📊 1) 데이터 확인", use_container_width=True):
        st.switch_page("views/analysis/__init__.py")
    if step_cols[1].button("🏆 2) 종목 추천 받기", use_container_width=True):
        st.switch_page("views/analysis/__init__.py")
    if step_cols[2].button("⚡ 3) 자동매매 실행", use_container_width=True):
        st.switch_page("views/trading/__init__.py")

    st.markdown("#### Market Overview")
    picked_order = st.multiselect(
        "지수 표시 순서",
        default_indices,
        default=st.session_state["home_indices_order"],
        key="home_indices_order",
    )
    indices = [idx for idx in picked_order if idx in default_indices] + [
        idx for idx in default_indices if idx not in picked_order
    ]
    if st.session_state["home_indices_order"] != indices:
        st.session_state["home_indices_order"] = indices

    current_pref = tuple(indices)
    if current_pref != st.session_state.get("_home_pref_last"):
        save_user_preferences(username, "home", {"indices_order": indices})
        log_user_activity(username, "settings_changed", "시장 지수 표시 순서 변경", "홈")
        st.session_state["_home_pref_last"] = current_pref

    if market_data:
        idx_cols = st.columns(4)
        for col, idx_name in zip(idx_cols, indices):
            if idx_name in market_data:
                data = market_data[idx_name]
                delta = f"{data['chg']:+.2f} ({data['pct']:+.2f}%)"
                col.metric(idx_name, f"{data['val']:,.0f}", delta)
            else:
                col.metric(idx_name, "-", "-")
    else:
        st.caption("시장 데이터 로딩 중...")

    st.markdown("#### Quick Access")
    qa_cols = st.columns(4)
    _TRADING = "views/trading/__init__.py"
    _ANALYSIS = "views/analysis/__init__.py"
    _PORTFOLIO = "views/portfolio.py"
    _SETTINGS = "views/settings/__init__.py"

    if user_is_pro:
        qa_items = [
            (_TRADING, "⚡ 자동매매"),
            (_ANALYSIS, "🏆 종목추천"),
            (_ANALYSIS, "🤖 AI예측"),
            (_SETTINGS, "📣 마케팅도구"),
        ]
    elif user_is_paid:
        qa_items = [
            (_ANALYSIS, "📊 데이터분석"),
            (_ANALYSIS, "🧪 백테스팅"),
            (_ANALYSIS, "📰 뉴스감성분석"),
            (_PORTFOLIO, "📁 포트폴리오"),
        ]
    else:
        qa_items = [
            (_ANALYSIS, "📊 데이터분석"),
            (_SETTINGS, "❓ 자주하는질문"),
            (_SETTINGS, "📩 고객문의"),
            (_SETTINGS, "💳 플랜 업그레이드"),
        ]
    for col, (target_path, label) in zip(qa_cols, qa_items):
        if col.button(label, use_container_width=True):
            st.switch_page(target_path)

    st.markdown("#### 최근 활동")
    recent = get_recent_activity(username, limit=10)
    if recent:
        for item in recent:
            stamp = str(item.get("created_at") or "")
            action_type = str(item.get("action_type") or "")
            page = str(item.get("page") or "-")
            detail = str(item.get("action_detail") or "")
            line = f"- `{stamp}` [{page}] {action_type}"
            if detail:
                line += f" - {detail}"
            st.markdown(line)
    else:
        st.caption("아직 기록된 활동이 없습니다.")

    plan_badge = "💎 Pro" if user_plan == "pro" else ("✨ Plus" if user_plan == "plus" else "🆓 Free")
    st.sidebar.markdown(f"**{user['username']}** ({user['role']}) — {plan_badge}")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⭐ 워치리스트")

    max_free_watchlist = 3
    watchlist = get_watchlist(user["username"])
    wl_count = len(watchlist) if not watchlist.empty else 0
    wl_can_add = user_is_paid or wl_count < max_free_watchlist

    if not user_is_paid:
        st.sidebar.caption(f"🔒 Free: {wl_count}/{max_free_watchlist}종목")

    with st.sidebar.expander("종목 추가", expanded=False):
        wl_ticker = st.text_input("종목코드", key="wl_add_ticker", placeholder="005930")
        wl_name = st.text_input("종목명", key="wl_add_name", placeholder="삼성전자")
        wl_market = str(st.selectbox("시장", ["KR", "US"], key="wl_add_market") or "KR")
        if st.button("추가", key="wl_add_btn", use_container_width=True):
            if not wl_can_add:
                st.error(f"Free 플랜 한도({max_free_watchlist}종목)에 도달했습니다.")
            elif wl_ticker and wl_name:
                add_watchlist(wl_ticker, wl_market, wl_name, user["username"])
                st.rerun()

    if not watchlist.empty:
        for _, row in watchlist.iterrows():
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
    st.sidebar.markdown("**Archon** v2.0 | Python 3.9+")
    if st.sidebar.button("Logout", key="home_logout", use_container_width=True):
        logout()
