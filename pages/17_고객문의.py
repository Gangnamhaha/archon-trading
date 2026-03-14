import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.auth import require_auth
from config.styles import inject_pro_css, show_legal_disclaimer
from data.database import add_customer_inquiry, get_customer_inquiries


st.set_page_config(page_title="고객문의", page_icon="📩", layout="wide")
user = require_auth()
inject_pro_css()

st.title("📩 고객문의")
st.caption("문의 내용을 남기면 관리자 페이지에서 확인하고 답변 상태를 업데이트합니다.")
st.page_link("pages/18_자주하는질문.py", label="❓ 자주하는 질문 먼저 보기", use_container_width=False)

with st.form("customer_inquiry_form"):
    category = str(st.selectbox("문의 유형", ["계정", "결제", "자동매매", "버그", "기능요청", "기타"]) or "기타")
    title = st.text_input("제목", max_chars=120)
    content = st.text_area("문의 내용", height=180, placeholder="문제 상황, 재현 방법, 기대 결과를 적어주세요.")
    submitted = st.form_submit_button("문의 접수", type="primary", use_container_width=True)

if submitted:
    if not title.strip() or not content.strip():
        st.error("제목과 문의 내용을 입력하세요.")
    else:
        add_customer_inquiry(user["username"], category, title.strip(), content.strip())
        st.success("문의가 접수되었습니다. 관리자 확인 후 상태가 업데이트됩니다.")
        st.rerun()

st.markdown("---")
st.subheader("내 문의 내역")

all_inquiries = get_customer_inquiries(status="전체", limit=300)
if all_inquiries.empty:
    st.info("아직 문의 내역이 없습니다.")
else:
    my_inquiries = all_inquiries[all_inquiries["username"] == user["username"]].copy()
    if my_inquiries.empty:
        st.info("아직 문의 내역이 없습니다.")
    else:
        display_cols = ["id", "category", "title", "status", "admin_note", "created_at", "updated_at"]
        for col in display_cols:
            if col not in my_inquiries.columns:
                my_inquiries[col] = ""
        st.dataframe(my_inquiries[display_cols], use_container_width=True, hide_index=True)

show_legal_disclaimer()
