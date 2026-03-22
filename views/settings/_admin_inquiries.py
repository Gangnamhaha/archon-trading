from __future__ import annotations

import streamlit as st

from data.database import get_customer_inquiries, update_customer_inquiry


def render_inquiries_tab() -> None:
    """Render Customer Inquiries tab."""

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
