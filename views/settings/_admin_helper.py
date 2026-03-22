import os
from typing import cast

import pandas as pd
import streamlit as st

from config.auth import change_password, create_user, delete_user, logout, update_user_plan, verify_user
from data.database import get_portfolio, get_trades
from views.settings._admin_analytics import render_analytics_tab
from views.settings._admin_errors import render_error_dashboard_tab
from views.settings._admin_inquiries import render_inquiries_tab


def render_users_tab(users_df: pd.DataFrame) -> None:
    """Render User Management tab."""
    st.subheader("User Management")
    st.dataframe(users_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Add User**")
        with st.form("add_user_form"):
            new_username = st.text_input("Username", key="new_user")
            new_password = st.text_input("Password", type="password", key="new_pass")
            new_role = str(st.selectbox("Role", ["user", "admin"], key="new_role") or "user")
            new_plan = str(st.selectbox("Plan", ["free", "plus", "pro"], key="new_plan") or "free")
            if st.form_submit_button("Add", type="primary", use_container_width=True):
                if new_username and new_password:
                    if create_user(new_username, new_password, new_role, new_plan):
                        st.success(f"'{new_username}' added.")
                        st.rerun()
                    else:
                        st.error("Username already exists.")
                else:
                    st.error("Fill all fields.")

    with col2:
        st.markdown("**Delete User**")
        if not users_df.empty:
            deletable = users_df[users_df["username"] != "admin"]
            if not deletable.empty:
                del_options = {f"{r['username']} (ID: {r['id']})": int(r["id"]) for _, r in deletable.iterrows()}
                del_selection = str(st.selectbox("Select user", list(del_options.keys()), key="del_user") or "")
                if st.button("Delete", type="primary", use_container_width=True):
                    if delete_user(del_options[del_selection]):
                        st.success("Deleted.")
                        st.rerun()
            else:
                st.info("No deletable users.")

        st.markdown("---")
        st.markdown("**Reset Password**")
        if not users_df.empty:
            reset_options = {f"{r['username']} (ID: {r['id']})": int(r["id"]) for _, r in users_df.iterrows()}
            reset_selection = str(st.selectbox("Select user", list(reset_options.keys()), key="reset_user") or "")
            reset_pw = st.text_input("New password", type="password", key="reset_pw")
            if st.button("Reset Password", use_container_width=True):
                if reset_pw:
                    change_password(reset_options[reset_selection], reset_pw)
                    st.success("Password changed.")
                else:
                    st.error("Enter new password.")

    st.markdown("---")
    st.subheader("💎 Plan Management")
    if not users_df.empty:
        plan_col1, plan_col2 = st.columns(2)
        with plan_col1:
            plan_options = {f"{r['username']} (ID: {r['id']}) — {r['plan']}": int(r["id"]) for _, r in users_df.iterrows()}
            plan_selection = str(st.selectbox("Select user", list(plan_options.keys()), key="plan_user") or "")
        with plan_col2:
            new_plan_val = str(st.selectbox("New Plan", ["free", "plus", "pro"], key="plan_val") or "free")
        if st.button("Change Plan", type="primary", use_container_width=True):
            update_user_plan(plan_options[plan_selection], new_plan_val)
            st.success(f"Plan updated to '{new_plan_val}'.")
            st.rerun()


def render_trade_log_tab() -> None:
    """Render Trade History tab."""
    st.subheader("Trade History")

    trade_limit = st.slider("Max rows", 10, 500, 100, key="trade_limit")
    trades_df = get_trades(limit=trade_limit)

    if trades_df.empty:
        st.info("No trades recorded.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trades", len(trades_df))
        buys = trades_df[trades_df["action"] == "BUY"] if "action" in trades_df.columns else pd.DataFrame()
        sells = trades_df[trades_df["action"] == "SELL"] if "action" in trades_df.columns else pd.DataFrame()
        col2.metric("Buys", len(buys))
        col3.metric("Sells", len(sells))
        strategies = int(trades_df["strategy"].nunique()) if "strategy" in trades_df.columns else 0
        col4.metric("Strategies Used", strategies)

        st.dataframe(trades_df, use_container_width=True, hide_index=True)


def render_system_tab(users_df: pd.DataFrame) -> None:
    """Render System Info tab."""
    st.subheader("System Info")

    portfolio_df = get_portfolio()
    users_count = len(users_df)
    trades_count = len(get_trades(limit=99999))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Version", "2.0")
    col2.metric("Users", users_count)
    col3.metric("Portfolio Items", len(portfolio_df))
    col4.metric("Total Trades", trades_count)

    st.markdown("---")
    st.subheader("Database")

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portfolio.db")
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        st.metric("DB Size", f"{size_mb:.2f} MB")

    if st.button("Clear Trade History", type="secondary"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM trade_history")
        conn.commit()
        conn.close()
        st.success("Trade history cleared.")
        st.rerun()

    st.markdown("---")
    st.subheader("Cache")
    if st.button("Clear Streamlit Cache", type="secondary"):
        st.cache_data.clear()
        st.success("Cache cleared.")


def render_account_tab(user: dict[str, object]) -> None:
    """Render My Account tab."""
    st.subheader("My Account")
    st.markdown(f"**Username:** {user['username']}")
    st.markdown(f"**Role:** {user['role']}")

    st.markdown("---")
    st.markdown("**Change My Password**")
    with st.form("change_my_pw"):
        cur_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        new_pw2 = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("Change Password", type="primary", use_container_width=True):
            if not cur_pw or not new_pw:
                st.error("Fill all fields.")
            elif new_pw != new_pw2:
                st.error("Passwords don't match.")
            else:
                check = verify_user(str(cast(str, user["username"])), cur_pw)
                if check is None:
                    st.error("Current password is wrong.")
                else:
                    change_password(int(cast(int, user["id"])), new_pw)
                    st.success("Password changed. Please re-login.")
                    logout()


