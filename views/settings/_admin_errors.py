from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data.database import get_error_dashboard_data


def render_error_dashboard_tab(user: dict[str, object]) -> None:
    """Render Error Dashboard tab."""

    st.subheader("🔍 에러 대시보드")

    if user.get("role") != "admin":
        st.error("에러 대시보드는 관리자만 확인할 수 있습니다.")
        return

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
