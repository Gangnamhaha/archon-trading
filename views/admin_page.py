import importlib
from datetime import datetime

import streamlit as st

from config.styles import inject_pro_css


def _admin_login_form() -> None:
    """관리자 전용 로그인 폼. 일반 사용자 로그인/회원가입 없이 관리자 인증만 제공."""
    core = importlib.import_module("auth.core")
    session_mod = importlib.import_module("auth.session")
    verify_user = core.verify_user
    _infer_client_meta = session_mod._infer_client_meta

    st.markdown("# 🛠️ 관리자 로그인")
    st.caption("이 페이지는 관리자 계정 전용입니다.")
    st.markdown("---")

    with st.form("admin_login_form"):
        username = st.text_input("관리자 아이디", placeholder="admin")
        password = st.text_input("비밀번호", type="password", placeholder="관리자 비밀번호를 입력하세요")
        submitted = st.form_submit_button("관리자 로그인", type="primary", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("아이디와 비밀번호를 입력하세요.")
            else:
                user = verify_user(username, password)
                if user and str(user.get("role", "")) == "admin":
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.session_state["_login_time"] = datetime.now()
                    st.session_state["_last_activity_time"] = datetime.now()
                    st.session_state["_session_timeout"] = 86400
                    try:
                        from data.database import create_session_token, log_user_activity, update_session_device_info

                        log_user_activity(str(user["username"]), "admin_login", "", "관리자 로그인")
                        token = create_session_token(
                            username=str(user["username"]),
                            user_id=int(str(user["id"])),
                            role=str(user["role"]),
                            plan=str(user["plan"]),
                            session_timeout=86400,
                            max_sessions=1,
                        )
                        device_info, user_agent, ip_addr = _infer_client_meta()
                        update_session_device_info(token, device_info, user_agent, ip_addr)
                        st.session_state["_auth_token"] = token
                    except Exception:
                        pass
                    st.rerun()
                elif user:
                    st.error("관리자 권한이 없는 계정입니다.")
                else:
                    st.error("아이디 또는 비밀번호가 틀렸습니다.")


def render_admin_page() -> None:
    inject_pro_css()

    # 이미 관리자로 로그인된 경우 바로 대시보드 표시
    if st.session_state.get("authenticated"):
        user = st.session_state.get("user", {})
        if str(user.get("role", "")) == "admin":
            from views.settings.admin import render_admin

            st.title("🛠️ 관리자 페이지")
            render_admin(user)
            return
        else:
            st.title("🛠️ 관리자 페이지")
            st.error("관리자 권한이 필요합니다. 관리자 계정으로 다시 로그인하세요.")
            return

    # 미인증 상태: 관리자 전용 로그인 폼 표시
    _admin_login_form()
