import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences
from data.database import log_user_activity


def render_analysis():
    user = require_auth()
    username = str(user["username"])
    if st.session_state.get("_analysis_pref_user") != username:
        reset_keys = [
            "analysis_section",
            "analysis_ticker",
            "analysis_market",
            "analysis_period",
            "analysis_interval",
            "data_market",
            "ta_market",
            "pred_market",
            "data_ticker_input",
            "data_ticker_code",
            "ta_ticker",
            "pred_ticker",
            "data_period",
            "ta_period",
            "pred_period",
            "data_interval",
            "data_auto_rerun",
            "ta_auto_rerun",
            "pred_auto_rerun",
            "_pred_auto_saved",
            "ai_subsection",
            "charts_subsection",
            "_analysis_pref_last",
            "data_ticker",
            "data_market_code",
            "data_run_period",
            "data_run_interval",
            "_prev_data_market",
            "_prev_data_popular",
            "compare_market",
            "compare_tickers_input",
            "_prev_compare_market",
            "ta_run_ticker",
            "ta_market_code",
            "ta_run_period",
            "_prev_ta_market",
            "scr_market",
            "scr_top_n",
            "scr_preset",
            "scr_rsi",
            "scr_macd",
            "scr_sma",
            "scr_vol",
            "scr_ret",
            "screener_result",
            "rec_mode",
            "rec_market",
            "rec_scan",
            "rec_result_count",
            "recommend_result_key",
            "recommend_result",
            "aggressive_result",
            "ai_prediction_result",
            "_prev_pred_market",
            "news_sources",
            "news_keyword",
            "news_analysis_result",
            "risk_market",
            "risk_ticker",
            "benchmark",
            "risk_period",
            "mc_market",
            "mc_ticker",
            "mc_sims",
            "mc_days",
            "mc_conf",
            "ef_market",
            "ef_tickers",
            "ef_period",
            "lev_market",
            "lev_ticker",
            "lev_period",
            "lev_mult",
            "risk_mc_result",
            "risk_ef_result",
        ]
        for key in reset_keys:
            st.session_state.pop(key, None)
        st.session_state["_analysis_pref_user"] = username

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
    saved_data_auto = bool(saved.get("data_auto_rerun", False))
    saved_ta_auto = bool(saved.get("ta_auto_rerun", False))
    saved_pred_auto = bool(saved.get("pred_auto_rerun", False))

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
    # Keep chart/technical auto-toggles aligned with persisted preferences.
    # These toggles are persisted immediately via on_change callbacks.
    st.session_state["data_auto_rerun"] = saved_data_auto
    st.session_state["ta_auto_rerun"] = saved_ta_auto
    # Keep AI prediction auto-toggle aligned with persisted preference.
    # Unlike data/ta toggles, prediction toggle is persisted immediately via on_change.
    st.session_state["pred_auto_rerun"] = saved_pred_auto
    st.session_state.setdefault(
        "_analysis_pref_last",
        {
            "last_section": str(st.session_state.get("analysis_section") or "📈 차트분석"),
            "last_ticker": str(
                st.session_state.get("analysis_ticker")
                or st.session_state.get("data_ticker_input")
                or st.session_state.get("data_ticker_code")
                or st.session_state.get("ta_ticker")
                or st.session_state.get("pred_ticker")
                or saved_ticker
            ),
            "last_period": str(st.session_state.get("analysis_period") or saved_period),
            "last_interval": str(st.session_state.get("analysis_interval") or st.session_state.get("data_interval") or saved_interval),
            "last_market": str(st.session_state.get("analysis_market") or saved_market),
            "data_auto_rerun": bool(st.session_state.get("data_auto_rerun", saved_data_auto)),
            "ta_auto_rerun": bool(st.session_state.get("ta_auto_rerun", saved_ta_auto)),
            "pred_auto_rerun": bool(st.session_state.get("pred_auto_rerun", saved_pred_auto)),
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
        "data_auto_rerun": bool(st.session_state.get("data_auto_rerun", st.session_state.get("_analysis_pref_last", {}).get("data_auto_rerun", saved_data_auto))),
        "ta_auto_rerun": bool(st.session_state.get("ta_auto_rerun", st.session_state.get("_analysis_pref_last", {}).get("ta_auto_rerun", saved_ta_auto))),
        "pred_auto_rerun": bool(st.session_state.get("pred_auto_rerun", st.session_state.get("_analysis_pref_last", {}).get("pred_auto_rerun", saved_pred_auto))),
    }
    if current_pref != st.session_state.get("_analysis_pref_last"):
        merged_pref = dict(saved)
        merged_pref.update(current_pref)
        save_user_preferences(username, "analysis", merged_pref)
        log_user_activity(username, "settings_changed", "분석 기본 설정 변경", "분석")
        st.session_state["_analysis_pref_last"] = current_pref
