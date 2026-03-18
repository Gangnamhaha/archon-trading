import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences
from data.database import log_user_activity


def render_analysis():
    user = require_auth()
    username = str(user["username"])
    visit_key = f"_visit_logged_analysis_{username}"
    if not st.session_state.get(visit_key):
        log_user_activity(username, "page_visit", "", "분석")
        st.session_state[visit_key] = True

    saved = load_user_preferences(username, "analysis")
    saved_market = str(saved.get("last_market", "US") or "US").upper()
    market_label = "KR (한국)" if saved_market == "KR" else "US (미국)"
    saved_ticker = str(saved.get("last_ticker", "AAPL") or "AAPL")
    saved_period = str(saved.get("last_period", "1y") or "1y")
    saved_interval = str(saved.get("last_interval", "1d") or "1d")

    st.session_state.setdefault("analysis_section", str(saved.get("last_section", "📈 차트분석") or "📈 차트분석"))
    st.session_state.setdefault("analysis_ticker", saved_ticker)
    st.session_state.setdefault("analysis_market", saved_market)
    st.session_state.setdefault("analysis_period", saved_period)
    st.session_state.setdefault("analysis_interval", saved_interval)

    st.session_state.setdefault("data_market", market_label)
    st.session_state.setdefault("ta_market", market_label)
    st.session_state.setdefault("pred_market", saved_market)
    st.session_state.setdefault("data_ticker_input", saved_ticker if saved_market == "US" else "AAPL")
    st.session_state.setdefault("data_ticker_code", saved_ticker if saved_market == "KR" else "005930")
    st.session_state.setdefault("ta_ticker", saved_ticker)
    st.session_state.setdefault("pred_ticker", saved_ticker)
    st.session_state.setdefault("data_period", saved_period if saved_period in ["1mo", "3mo", "6mo", "1y", "2y", "5y"] else "1y")
    st.session_state.setdefault("ta_period", saved_period if saved_period in ["3mo", "6mo", "1y", "2y"] else "1y")
    st.session_state.setdefault("pred_period", saved_period if saved_period in ["6mo", "1y", "2y"] else "1y")
    st.session_state.setdefault("data_interval", saved_interval if saved_interval in ["1d", "1wk", "1mo", "5m", "15m", "1h"] else "1d")
    st.session_state.setdefault(
        "_analysis_pref_last",
        {
            "last_section": str(st.session_state.get("analysis_section") or "📈 차트분석"),
            "last_ticker": saved_ticker,
            "last_period": saved_period,
            "last_interval": saved_interval,
            "last_market": saved_market,
        },
    )

    inject_pro_css()
    st.title("📊 분석")

    selected = st.radio(
        "섹션",
        ["📈 차트분석", "🤖 AI판단", "🧪 투자도구"],
        horizontal=True,
        label_visibility="collapsed",
        key="analysis_section",
    )

    if selected == "📈 차트분석":
        from views.analysis.charts import render_charts

        render_charts(user)
    elif selected == "🤖 AI판단":
        from views.analysis.ai import render_ai

        render_ai(user)
    elif selected == "🧪 투자도구":
        from views.analysis.tools import render_tools

        render_tools(user)

    market_raw = str(st.session_state.get("data_market") or st.session_state.get("ta_market") or st.session_state.get("pred_market") or "US")
    resolved_market = market_raw.split(" ")[0]
    if resolved_market not in {"US", "KR", "KOSPI", "KOSDAQ"}:
        resolved_market = "US"

    resolved_ticker = str(
        st.session_state.get("data_ticker")
        or st.session_state.get("ta_ticker")
        or st.session_state.get("pred_ticker")
        or st.session_state.get("data_ticker_input")
        or st.session_state.get("data_ticker_code")
        or saved_ticker
    )
    resolved_period = str(
        st.session_state.get("data_period")
        or st.session_state.get("ta_period")
        or st.session_state.get("pred_period")
        or saved_period
    )
    resolved_interval = str(st.session_state.get("data_interval") or saved_interval)

    current_pref = {
        "last_section": str(selected),
        "last_ticker": resolved_ticker,
        "last_period": resolved_period,
        "last_interval": resolved_interval,
        "last_market": resolved_market,
    }
    if current_pref != st.session_state.get("_analysis_pref_last"):
        save_user_preferences(username, "analysis", current_pref)
        log_user_activity(username, "settings_changed", "분석 기본 설정 변경", "분석")
        st.session_state["_analysis_pref_last"] = current_pref
