# pyright: basic
from datetime import datetime

import streamlit as st


def _format_session_time(value: object) -> str:
    text = str(value or "")
    if not text:
        return "-"
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return text[:16]


def render_device_manager(user: dict[str, object]):
    username = str(user.get("username", ""))
    if not username:
        return

    refresh_requested = st.button("목록 새로고침", key="_device_refresh", use_container_width=True)
    cache_key = f"{username}::{st.session_state.get('_auth_token', '')}"
    cache_at = st.session_state.get("_active_sessions_cache_at")
    use_cache = (
        not refresh_requested
        and st.session_state.get("_active_sessions_cache_key") == cache_key
        and isinstance(cache_at, datetime)
        and (datetime.now() - cache_at).total_seconds() < 20
    )

    sessions = st.session_state.get("_active_sessions_cache", []) if use_cache else []
    if not use_cache:
        try:
            from data.database import get_active_sessions

            sessions = get_active_sessions(username)
        except Exception:
            sessions = []
        st.session_state["_active_sessions_cache"] = sessions
        st.session_state["_active_sessions_cache_key"] = cache_key
        st.session_state["_active_sessions_cache_at"] = datetime.now()

    if not sessions:
        st.caption("활성 세션이 없습니다.")
        return

    current_token = str(st.session_state.get("_auth_token", ""))
    st.caption(f"활성 기기 {len(sessions)}대")
    for idx, sess in enumerate(sessions):
        token = str(sess.get("token", ""))
        is_current = token == current_token
        device = str(sess.get("device_info", "") or "알 수 없는 기기")
        ip_addr = str(sess.get("ip_addr", "") or "-")
        last_seen = _format_session_time(sess.get("last_seen"))
        expires_at = _format_session_time(sess.get("expires_at"))
        badge = " (현재 기기)" if is_current else ""
        with st.container(border=True):
            st.markdown(f"**{device}{badge}**")
            st.caption(f"IP: {ip_addr} | 최근 활동: {last_seen} | 만료: {expires_at}")
            if is_current:
                st.caption("현재 로그인 중인 기기입니다.")
            else:
                if st.button("강제 로그아웃", key=f"_kick_session_{idx}_{token[-8:]}", use_container_width=True):
                    try:
                        from data.database import force_logout_session

                        kicked = force_logout_session(token)
                    except Exception:
                        kicked = False
                    st.session_state.pop("_active_sessions_cache", None)
                    st.session_state.pop("_active_sessions_cache_at", None)
                    st.session_state.pop("_active_sessions_cache_key", None)
                    if kicked:
                        st.success("선택한 기기를 로그아웃했습니다.")
                    else:
                        st.warning("이미 종료된 세션입니다.")
                    st.rerun()
