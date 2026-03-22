from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from data.database import get_all_activity_logs


def render_analytics_tab(users_df: pd.DataFrame) -> None:
    """Render Analytics tab."""

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
            title="Top 페이지 방문 수",
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
                    title="일별 활성 사용자",
                )
                fig_dau.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0")
                st.plotly_chart(fig_dau, use_container_width=True)

    st.markdown("---")
    st.subheader("플랜 분포")
    if users_df.empty or "plan" not in users_df.columns:
        st.info("플랜 분포 데이터가 없습니다.")
    else:
        plan_dist = users_df["plan"].value_counts().reindex(["free", "plus", "pro"], fill_value=0).reset_index()
        plan_dist.columns = ["plan", "count"]
        fig_plan = px.pie(
            plan_dist,
            values="count",
            names="plan",
            title="Free vs Plus vs Pro",
            color="plan",
            color_discrete_map={"free": "#A0AEC0", "plus": "#38BDF8", "pro": "#00D4AA"},
        )
        fig_plan.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0")
        st.plotly_chart(fig_plan, use_container_width=True)
