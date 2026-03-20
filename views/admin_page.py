import streamlit as st

from config.auth import require_auth
from config.styles import inject_pro_css
from views.settings.admin import render_admin


def render_admin_page() -> None:
    user = require_auth()
    inject_pro_css()
    st.title("🛠️ 관리자 페이지")
    render_admin(user)
