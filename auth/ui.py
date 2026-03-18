import importlib
from datetime import datetime

import streamlit as st


def _show_login_form():
    core_module = importlib.import_module("auth.core")
    session_module = importlib.import_module("auth.session")
    create_user = core_module.create_user
    verify_user = core_module.verify_user
    _SESSION_TIMEOUT_OPTIONS = session_module._SESSION_TIMEOUT_OPTIONS
    _infer_client_meta = session_module._infer_client_meta

    st.markdown(
        """
    <style>
        .archon-landing {
            background: #0E1117;
            border: 1px solid rgba(0, 212, 170, 0.25);
            border-radius: 16px;
            padding: 1.25rem;
            margin: 0.5rem 0 1rem 0;
        }
        .archon-card {
            background: rgba(0, 212, 170, 0.08);
            border: 1px solid rgba(0, 212, 170, 0.25);
            border-radius: 14px;
            padding: 1rem;
            height: 100%;
        }
        .archon-price-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 14px;
            padding: 1rem;
            height: 100%;
        }
        .archon-price-card.pro {
            border: 1px solid rgba(0, 212, 170, 0.5);
            box-shadow: 0 0 0 1px rgba(0, 212, 170, 0.2) inset;
        }
        .archon-price-card.plus {
            border: 1px solid rgba(56, 189, 248, 0.45);
            box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.16) inset;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("# 🏛️ ARCHON")
    st.markdown("### AI 기반 주식 자동매매 플랫폼")

    st.markdown(
        """
    <div class="archon-landing">
        <h3 style="margin:0 0 0.5rem 0;color:#E2E8F0;">로그인 후 바로 자동매매를 시작하세요</h3>
        <p style="margin:0;color:#A0AEC0;line-height:1.5;">
            핵심 기능: 실시간 분석, 전략 자동매매, 오토파일럿, AI 어시스턴트
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    _k1, _k2, _k3 = st.columns(3)
    _k1.metric("플랜", "Free / Plus / Pro")
    _k2.metric("연동", "KIS / 키움 / NH")
    _k3.metric("오토파일럿", "최대 5 슬롯")

    st.caption("불필요한 소개 화면을 줄이고 로그인/회원가입에 집중된 시작 화면입니다.")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    _ = (col1, col3)
    with col2:
        with st.expander("📜 이용약관 보기"):
            st.markdown(
                """
                - 본 서비스는 투자 참고 정보를 제공하며, 투자 판단 및 결과 책임은 이용자 본인에게 있습니다.
                - AI 추천/분석/자동매매 기능은 수익을 보장하지 않으며 원금 손실이 발생할 수 있습니다.
                - Pro 결제는 관련 법령에 따라 청약철회가 가능하나, 사용분은 차감될 수 있습니다.
                - 서비스 내용은 사전 고지 후 변경/중단될 수 있습니다.
                """
            )
        with st.expander("🔐 개인정보처리방침 보기"):
            st.markdown(
                """
                - 수집 항목: 사용자명, 비밀번호(해시), API 키(암호화 저장), 대화/거래/포트폴리오 내역, 접속 로그
                - 수집 목적: 서비스 제공, 자동매매 실행, 설정 복원, 운영 안정화
                - 보관 기간: 회원 탈퇴 시까지(법령상 보관 의무 제외)
                - AI 채팅 사용 시 선택한 AI 제공사로 대화가 전송될 수 있습니다.
                """
            )
        agree = st.checkbox("이용약관 및 개인정보처리방침에 동의합니다", key="login_agree")

        login_tab, signup_tab = st.tabs(["🔐 로그인", "📝 회원가입"])

        with login_tab:
            session_label = str(
                st.selectbox("세션 유지 시간", list(_SESSION_TIMEOUT_OPTIONS.keys()), index=2, key="session_timeout_sel")
                or "24시간"
            )
            with st.form("login_form"):
                username = st.text_input("아이디", placeholder="아이디를 입력하세요")
                password = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
                submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

                if submitted:
                    if not agree:
                        st.warning("약관에 동의해야 로그인할 수 있습니다.")
                    elif not username or not password:
                        st.error("아이디와 비밀번호를 입력하세요.")
                    else:
                        user = verify_user(username, password)
                        if user:
                            timeout_sec = _SESSION_TIMEOUT_OPTIONS[session_label]
                            st.session_state["authenticated"] = True
                            st.session_state["user"] = user
                            st.session_state["_login_time"] = datetime.now()
                            st.session_state["_session_timeout"] = timeout_sec
                            try:
                                from data.database import log_user_activity

                                log_user_activity(str(user["username"]), "login", "", "로그인")
                            except Exception:
                                pass
                            try:
                                from data.database import create_session_token, update_session_device_info

                                max_sessions = 1 if str(user.get("role", "")) == "admin" else 2
                                token = create_session_token(
                                    username=str(user["username"]),
                                    user_id=int(str(user["id"])),
                                    role=str(user["role"]),
                                    plan=str(user["plan"]),
                                    session_timeout=timeout_sec,
                                    max_sessions=max_sessions,
                                )
                                device_info, user_agent, ip_addr = _infer_client_meta()
                                update_session_device_info(token, device_info, user_agent, ip_addr)
                                st.session_state["_auth_token"] = token
                            except Exception:
                                pass
                            st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호가 틀렸습니다.")

        with signup_tab:
            with st.form("signup_form"):
                new_username = st.text_input("아이디", placeholder="4~20자, 영문/숫자/이메일 형식")
                new_password = st.text_input("비밀번호", type="password", placeholder="8자 이상, 영문+숫자 조합")
                new_password_confirm = st.text_input("비밀번호 확인", type="password", placeholder="비밀번호를 다시 입력하세요")
                signup_submitted = st.form_submit_button("회원가입", type="primary", use_container_width=True)

                if signup_submitted:
                    if not agree:
                        st.warning("약관에 동의해야 회원가입할 수 있습니다.")
                    elif not new_username or not new_password or not new_password_confirm:
                        st.error("모든 항목을 입력하세요.")
                    elif len(new_username) < 4 or len(new_username) > 50:
                        st.error("아이디는 4자 이상 50자 이하로 입력하세요.")
                    elif len(new_password) < 8:
                        st.error("비밀번호는 8자 이상이어야 합니다.")
                    elif not any(c.isdigit() for c in new_password) or not any(c.isalpha() for c in new_password):
                        st.error("비밀번호는 영문과 숫자를 모두 포함해야 합니다.")
                    elif new_password != new_password_confirm:
                        st.error("비밀번호가 일치하지 않습니다.")
                    elif new_username.lower() == "admin":
                        st.error("사용할 수 없는 아이디입니다.")
                    else:
                        success = create_user(new_username, new_password, role="user", plan="free")
                        if success:
                            st.success(f"🎉 회원가입 완료! '{new_username}'으로 로그인하세요.")
                            st.balloons()
                        else:
                            st.error("이미 사용 중인 아이디입니다. 다른 아이디를 사용하세요.")
