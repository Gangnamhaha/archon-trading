import importlib
from datetime import datetime

import streamlit as st

from config.styles import inject_pro_css


def _complete_admin_login(user: dict, _infer_client_meta) -> None:
    """비밀번호+2FA 검증 완료 후 세션을 설정하고 로그인을 완료한다."""
    st.session_state["authenticated"] = True
    st.session_state["user"] = user
    st.session_state["_login_time"] = datetime.now()
    st.session_state["_last_activity_time"] = datetime.now()
    st.session_state["_session_timeout"] = 86400
    st.session_state.pop("_admin_2fa_pending", None)
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


def _admin_login_form() -> None:
    """관리자 전용 로그인 폼. 일반 사용자 로그인/회원가입 없이 관리자 인증만 제공."""
    core = importlib.import_module("auth.core")
    session_mod = importlib.import_module("auth.session")
    verify_user = core.verify_user
    is_totp_enabled = core.is_totp_enabled
    verify_totp = core.verify_totp
    _infer_client_meta = session_mod._infer_client_meta

    st.markdown("# 🛠️ 관리자 로그인")
    st.caption("이 페이지는 관리자 계정 전용입니다.")
    st.markdown("---")

    # 2FA 코드 입력 단계
    pending = st.session_state.get("_admin_2fa_pending")
    if pending:
        st.info("2단계 인증이 필요합니다. 인증 앱의 코드를 입력하세요.")
        with st.form("admin_2fa_form"):
            totp_code = st.text_input("인증 코드 (6자리)", max_chars=6, placeholder="000000")
            submitted_2fa = st.form_submit_button("인증", type="primary", use_container_width=True)
            cancel = st.form_submit_button("취소")

        if submitted_2fa:
            if verify_totp(int(str(pending["id"])), totp_code):
                _complete_admin_login(pending, _infer_client_meta)
            else:
                st.error("인증 코드가 올바르지 않습니다.")
        if cancel:
            st.session_state.pop("_admin_2fa_pending", None)
            st.rerun()
        return

    # 비밀번호 로그인 단계
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
                    if is_totp_enabled(int(str(user["id"]))):
                        st.session_state["_admin_2fa_pending"] = user
                        st.rerun()
                    else:
                        _complete_admin_login(user, _infer_client_meta)
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
