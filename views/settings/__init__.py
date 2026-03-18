import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css


def render_settings():
    user = require_auth()
    inject_pro_css()

    st.title("⚙️ 설정")

    sections = ["💳 결제", "🤖 AI어시스턴트", "📞 고객지원"]
    if user.get("plan") == "pro":
        sections.append("📣 마케팅")
    if user.get("role") == "admin":
        sections.append("🔧 관리자")

    selected = st.radio("섹션", sections, horizontal=True, label_visibility="collapsed")

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
