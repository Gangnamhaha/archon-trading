import os
from datetime import timedelta
from typing import cast

import pandas as pd
import plotly.express as px
import streamlit as st

from config.auth import is_admin, create_user, delete_user, change_password, get_all_users, logout, update_user_plan
from data.database import (
    get_trades,
    get_portfolio,
    get_all_activity_logs,
    get_customer_inquiries,
    update_customer_inquiry,
    get_error_dashboard_data,
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

    with tab2:
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

    with tab3:
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

    with tab4:
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
                    from config.auth import verify_user
                    check = verify_user(str(cast(str, user["username"])), cur_pw)
                    if check is None:
                        st.error("Current password is wrong.")
                    else:
                        change_password(int(cast(int, user["id"])), new_pw)
                        st.success("Password changed. Please re-login.")
                        logout()

    with tab5:
        st.subheader("사용자 분석 대시보드")

        total_users = len(users_df)
        plus_users = len(users_df[users_df["plan"] == "plus"]) if "plan" in users_df.columns else 0
        pro_users = len(users_df[users_df["plan"] == "pro"]) if "plan" in users_df.columns else 0
        free_users = len(users_df[users_df["plan"] == "free"]) if "plan" in users_df.columns else 0

        today_signups = 0
        if "created_at" in users_df.columns and not users_df.empty:
            created_series = pd.to_datetime(users_df["created_at"], errors="coerce")
            today_signups = int((created_series.dt.date == pd.Timestamp.now().date()).sum())

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total users", total_users)
        m2.metric("Free users", free_users)
        m3.metric("Plus users", plus_users)
        m4.metric("Pro users", pro_users)
        m5.metric("오늘 가입 수", today_signups)

        st.markdown("---")
        st.subheader("활동 로그")
        log_limit = st.slider("활동 로그 개수", 20, 300, 100, key="analytics_log_limit")
        activity_df = get_all_activity_logs(limit=log_limit)

        if activity_df.empty:
            st.info("활동 로그가 없습니다.")
        else:
            activity_df["created_at"] = pd.to_datetime(activity_df["created_at"], errors="coerce")
            st.dataframe(activity_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("페이지별 방문 수")
            page_visit_df = activity_df.copy()
            page_visit_df["page"] = page_visit_df["detail"].fillna(page_visit_df["action"]).astype(str)
            page_counts = page_visit_df["page"].value_counts().head(10).reset_index()
            page_counts.columns = ["page", "visits"]
            fig_pages = px.bar(
                page_counts,
                x="page",
                y="visits",
                color_discrete_sequence=["#00D4AA"],
                title="Top 페이지 방문 수"
            )
            fig_pages.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0")
            st.plotly_chart(fig_pages, use_container_width=True)

            st.markdown("---")
            st.subheader("일별 활성 사용자 (최근 30일)")
            dau_df = activity_df.dropna(subset=["created_at"]).copy()
            if dau_df.empty:
                st.info("활성 사용자 데이터가 없습니다.")
            else:
                start_date = pd.Timestamp.now().to_pydatetime() - timedelta(days=29)
                dau_df = dau_df[dau_df["created_at"] >= start_date]
                if dau_df.empty:
                    st.info("최근 30일 활성 사용자 데이터가 없습니다.")
                else:
                    dau_dates = pd.Series(pd.to_datetime(dau_df["created_at"], errors="coerce"), index=dau_df.index)
                    dau_df["date"] = dau_dates.dt.date
                    daily_active = dau_df.groupby("date")["username"].nunique().reset_index()
                    daily_active.columns = ["date", "active_users"]
                    fig_dau = px.line(
                        daily_active,
                        x="date",
                        y="active_users",
                        markers=True,
                        color_discrete_sequence=["#00D4AA"],
                        title="일별 활성 사용자"
                    )
                    fig_dau.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0")
                    st.plotly_chart(fig_dau, use_container_width=True)

        st.markdown("---")
        st.subheader("플랜 분포")
        if users_df.empty or "plan" not in users_df.columns:
            st.info("플랜 분포 데이터가 없습니다.")
        else:
            plan_dist = (
                users_df["plan"]
                .value_counts()
                .reindex(["free", "plus", "pro"], fill_value=0)
                .reset_index()
            )
            plan_dist.columns = ["plan", "count"]
            fig_plan = px.pie(
                plan_dist,
                values="count",
                names="plan",
                title="Free vs Plus vs Pro",
                color="plan",
                color_discrete_map={"free": "#A0AEC0", "plus": "#38BDF8", "pro": "#00D4AA"}
            )
            fig_plan.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0")
            st.plotly_chart(fig_plan, use_container_width=True)

    with tab6:
        st.subheader("고객 문의 관리")
        c1, c2 = st.columns([1, 1])
        with c1:
            inq_status = str(st.selectbox("상태 필터", ["전체", "접수", "처리중", "완료"], key="inq_status") or "전체")
        with c2:
            inq_limit = st.slider("조회 개수", 20, 500, 200, key="inq_limit")

        inquiries_df = get_customer_inquiries(status=inq_status, limit=inq_limit)
        if inquiries_df.empty:
            st.info("문의 내역이 없습니다.")
        else:
            st.dataframe(inquiries_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**문의 상태 업데이트**")
            options = {
                f"#{int(r['id'])} | {r['username']} | {r['title']} | {r['status']}": int(r["id"])
                for _, r in inquiries_df.iterrows()
            }
            selected = str(st.selectbox("문의 선택", list(options.keys()), key="inq_select") or "")
            new_status = str(st.selectbox("변경 상태", ["접수", "처리중", "완료"], key="inq_new_status") or "접수")
            admin_note = st.text_area("관리자 메모", key="inq_admin_note", height=100)
            if st.button("문의 업데이트", type="primary", use_container_width=True, key="inq_update_btn"):
                if not selected or selected not in options:
                    st.error("업데이트할 문의를 선택하세요.")
                else:
                    update_customer_inquiry(int(options[selected]), new_status, admin_note.strip())
                    st.success("문의 상태가 업데이트되었습니다.")
                    st.rerun()

    with tab7:
        st.subheader("🔍 에러 대시보드")

        if user.get("role") != "admin":
            st.error("에러 대시보드는 관리자만 확인할 수 있습니다.")
        else:
            dashboard = get_error_dashboard_data(hours=24)
            total_errors_raw = dashboard.get("total_errors", 0)
            total_errors = total_errors_raw if isinstance(total_errors_raw, (int, float)) else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("24h 에러 수", total_errors)
            m2.metric("가장 많은 에러 코드", str(dashboard.get("top_error_code", "-")))
            m3.metric("가장 많은 에러 페이지", str(dashboard.get("top_error_page", "-")))

            st.markdown("---")
            st.subheader("최근 20건")
            recent_errors = dashboard.get("recent_errors", pd.DataFrame())
            if isinstance(recent_errors, pd.DataFrame) and not recent_errors.empty:
                st.dataframe(recent_errors, use_container_width=True, hide_index=True)
            else:
                st.info("최근 에러 로그가 없습니다.")

            st.markdown("---")
            st.subheader("페이지별 에러 빈도")
            page_frequency = dashboard.get("page_frequency", pd.DataFrame())
            if isinstance(page_frequency, pd.DataFrame) and not page_frequency.empty:
                fig_err = px.bar(
                    page_frequency,
                    x="page",
                    y="error_count",
                    color_discrete_sequence=["#F97316"],
                    title="최근 24시간 페이지별 에러 발생 수",
                )
                fig_err.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0")
                st.plotly_chart(fig_err, use_container_width=True)
                st.dataframe(page_frequency, use_container_width=True, hide_index=True)
            else:
                st.info("최근 24시간 에러 데이터가 없습니다.")
