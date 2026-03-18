import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css


def render_analysis():
    user = require_auth()
    inject_pro_css()
    st.title("📊 분석")

    selected = st.radio(
        "섹션",
        ["📈 차트분석", "🤖 AI판단", "🧪 투자도구"],
        horizontal=True,
        label_visibility="collapsed",
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
