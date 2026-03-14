import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from config.styles import inject_pro_css
from config.auth import require_auth, is_admin
from data.database import add_notice, get_notices

st.set_page_config(page_title="공지사항", page_icon="📢", layout="wide")
user = require_auth()
inject_pro_css()
st.title("📢 공지사항")

if is_admin():
    with st.expander("공지 작성", expanded=False):
        with st.form("notice_form"):
            n_title = st.text_input("제목")
            n_content = st.text_area("내용", height=200)
            if st.form_submit_button("발행", type="primary", use_container_width=True):
                if n_title and n_content:
                    add_notice(n_title, n_content, user["username"])
                    st.success("공지가 발행되었습니다.")
                    st.rerun()

st.markdown("---")
notices = get_notices()
if notices.empty:
    st.info("등록된 공지사항이 없습니다.")
else:
    for _, row in notices.iterrows():
        with st.expander(f"**{row['title']}** - {row['created_at'][:10]}"):
            st.markdown(row["content"])
            st.caption(f"작성자: {row['author']} | {row['created_at']}")
