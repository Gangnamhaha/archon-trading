import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences
from data.database import log_user_activity


def render_settings():
    user = require_auth()
    username = str(user["username"])
    visit_key = f"_visit_logged_settings_{username}"
    if not st.session_state.get(visit_key):
        log_user_activity(username, "page_visit", "", "설정")
        st.session_state[visit_key] = True

    inject_pro_css()

    st.title("⚙️ 설정")

    sections = ["💳 결제", "🤖 AI어시스턴트", "📞 고객지원"]
    if user.get("plan") == "pro":
        sections.append("📣 마케팅")
    if user.get("role") == "admin":
        sections.append("🔧 관리자")

    saved = load_user_preferences(username, "settings")
    saved_section = str(saved.get("last_section", sections[0]) or sections[0])
    if saved_section not in sections:
        saved_section = sections[0]
    st.session_state.setdefault("settings_section", saved_section)
    if str(st.session_state.get("settings_section")) not in sections:
        st.session_state["settings_section"] = sections[0]
    st.session_state.setdefault("_settings_pref_last", str(st.session_state.get("settings_section") or sections[0]))

    selected = st.radio("섹션", sections, horizontal=True, label_visibility="collapsed", key="settings_section")

    if selected != st.session_state.get("_settings_pref_last"):
        save_user_preferences(username, "settings", {"last_section": selected})
        log_user_activity(username, "settings_changed", f"설정 섹션 변경: {selected}", "설정")
        st.session_state["_settings_pref_last"] = selected

    if selected == "💳 결제":
        from views.settings.payment import render_payment

        render_payment(user)
    elif selected == "🤖 AI어시스턴트":
        from views.settings.ai_chat import render_ai_chat

        render_ai_chat(user)
    elif selected == "📞 고객지원":
        from views.settings.support import render_support

        render_support(user)
    elif selected == "📣 마케팅":
        from views.settings.marketing import render_marketing

        render_marketing(user)
    elif selected == "🔧 관리자":
        from views.settings.admin import render_admin

        render_admin(user)
