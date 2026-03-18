import streamlit as st

from config.auth import is_admin, get_all_users
from views.settings._admin_helper import (
    render_users_tab,
    render_trade_log_tab,
    render_system_tab,
    render_account_tab,
    render_analytics_tab,
    render_inquiries_tab,
    render_error_dashboard_tab,
)


def render_admin(user: dict[str, object]):
    if not is_admin():
        st.error("관리자 권한이 필요합니다.")
        st.stop()

    st.subheader("🔧 관리자")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        ["Users", "Trade Log", "System", "My Account", "Analytics", "Inquiries", "🔍 에러 대시보드"]
    )

    users_df = get_all_users()

    with tab1:
        render_users_tab(users_df)

    with tab2:
        render_trade_log_tab()

    with tab3:
        render_system_tab(users_df)

    with tab4:
        render_account_tab(user)

    with tab5:
        render_analytics_tab(users_df)

    with tab6:
        render_inquiries_tab()

    with tab7:
        render_error_dashboard_tab(user)
