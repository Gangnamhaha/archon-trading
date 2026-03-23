import importlib
import json
import platform
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

_SESSION_TIMEOUT_OPTIONS = {
    "1시간": 3600,
    "6시간": 21600,
    "24시간": 86400,
    "7일": 604800,
    "무제한": 0,
}


def _get_request_headers() -> dict[str, str]:
    try:
        headers = getattr(st.context, "headers", None)
        if headers:
            return {str(k).lower(): str(v) for k, v in dict(headers).items()}
    except Exception:
        pass
    return {}


def _infer_client_meta() -> tuple[str, str, str]:
    headers = _get_request_headers()
    user_agent = headers.get("user-agent", "")
    xff = headers.get("x-forwarded-for", "")
    ip_addr = xff.split(",")[0].strip() if xff else ""
    if not ip_addr:
        ip_addr = headers.get("x-real-ip", "")
    sec_platform = headers.get("sec-ch-ua-platform", "").strip('"')
    if sec_platform:
        device_info = sec_platform
    elif user_agent:
        device_info = user_agent[:80]
    else:
        device_info = platform.system() or "unknown"
    return device_info, user_agent, ip_addr


def _clear_auth_state():
    for key in [
        "authenticated",
        "user",
        "_login_time",
        "_session_timeout",
        "_auth_token",
        "_last_session_touch",
        "_last_activity_time",
        "_active_sessions_cache",
        "_active_sessions_cache_at",
        "_active_sessions_cache_key",
    ]:
        st.session_state.pop(key, None)


def _check_session_expiry():
    if not st.session_state.get("authenticated"):
        return
    timeout = st.session_state.get("_session_timeout", 86400)
    if timeout == 0:
        return
    # Use last activity time instead of login time so that
    # ongoing usage (including background heartbeats) keeps the session alive.
    last_activity = st.session_state.get("_last_activity_time")
    now = datetime.now()
    if not last_activity:
        st.session_state["_last_activity_time"] = now
        return
    elapsed = (now - last_activity).total_seconds()
    # Refresh activity timestamp on every page interaction
    st.session_state["_last_activity_time"] = now
    if elapsed > timeout:
        token = st.session_state.get("_auth_token", "")
        if token:
            try:
                from data.database import delete_session_token

                delete_session_token(str(token))
            except Exception:
                pass
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        _clear_localstorage_token()
        st.warning("세션이 만료되었습니다. 다시 로그인해주세요.")
        st.rerun()


_WAKELOCK_JS = """
<script>
(function() {
    var rootWindow = window.parent || window;
    var wakeLock = null;

    async function requestWakeLock() {
        try {
            if ('wakeLock' in navigator) {
                wakeLock = await navigator.wakeLock.request('screen');
                wakeLock.addEventListener('release', function() { wakeLock = null; });
            }
        } catch (e) {}
    }

    // Re-acquire wake lock when page becomes visible (e.g. screen unlock)
    document.addEventListener('visibilitychange', async function() {
        if (document.visibilityState === 'visible') {
            if (wakeLock === null) await requestWakeLock();
            // Touch server to keep session alive after screen unlock
            try { fetch(rootWindow.location.origin + '/_stcore/health', {method:'GET'}); } catch(e) {}
        }
    });

    // Heartbeat: ping server every 2 minutes to prevent Streamlit Cloud sleep
    // and keep the WebSocket connection alive during screen lock
    setInterval(function() {
        try { fetch(rootWindow.location.origin + '/_stcore/health', {method:'GET'}); } catch(e) {}
    }, 120000);

    requestWakeLock();
})();
</script>
"""

_LOCALSTORAGE_READER_JS = """
(function() {
    var rootWindow = window.parent || window;
    var token = rootWindow.localStorage.getItem('archon_auth_token');
    if (token) {
        var url = new URL(rootWindow.location.href);
        if (!url.searchParams.get('_auth')) {
            url.searchParams.set('_auth', token);
            rootWindow.history.replaceState({}, '', url.toString());
        }
    }
})();
"""


def _run_parent_js(js_body: str) -> None:
    components.html(f"<script>{js_body}</script>", height=0, width=0)


def _inject_localstorage_token(token: str, max_age_sec: int = 86400):
    _ = max_age_sec
    safe_token = json.dumps(str(token))
    js = f"""
    (function() {{
        var rootWindow = window.parent || window;
        try {{
            rootWindow.localStorage.setItem('archon_auth_token', {safe_token});
            var url = new URL(rootWindow.location.href);
            url.searchParams.delete('_auth');
            rootWindow.history.replaceState({{}}, '', url.toString());
        }} catch(e) {{}}
    }})();
    """
    _run_parent_js(js)


def _clear_localstorage_token():
    js = """
    (function() {
        var rootWindow = window.parent || window;
        try {
            rootWindow.localStorage.removeItem('archon_auth_token');
            var url = new URL(rootWindow.location.href);
            url.searchParams.delete('_auth');
            rootWindow.history.replaceState({}, '', url.toString());
        } catch(e) {}
    })();
    """
    _run_parent_js(js)


def _try_restore_session_from_token():
    token = st.session_state.get("_auth_token", "")

    if not token:
        token = st.query_params.get("_auth", "")
        if isinstance(token, list):
            token = token[0] if token else ""

    if not token:
        return False

    try:
        from data.database import cleanup_expired_session_tokens, touch_session, validate_session_token

        cleanup_expired_session_tokens()
        now = datetime.now()
        last_touch = st.session_state.get("_last_session_touch")
        user = validate_session_token(str(token))
        if not user:
            # If current runtime session is already authenticated, avoid force logout
            # on transient token validation issues during page transitions.
            if st.session_state.get("authenticated") and st.session_state.get("user"):
                runtime_token = str(st.session_state.get("_auth_token", "") or "")
                if runtime_token and runtime_token != str(token):
                    timeout_sec = int(str(st.session_state.get("_session_timeout", 86400) or 86400))
                    _inject_localstorage_token(runtime_token, timeout_sec)
                else:
                    try:
                        st.query_params.pop("_auth", None)
                    except Exception:
                        pass
                    _clear_localstorage_token()
                return False
            _clear_auth_state()
            _clear_localstorage_token()
            return False

        if not isinstance(last_touch, datetime) or (now - last_touch).total_seconds() >= 2:
            touch_session(str(token))
            st.session_state["_last_session_touch"] = now

        st.session_state["authenticated"] = True
        st.session_state["user"] = user
        st.session_state["_login_time"] = now
        _raw_timeout = user.get("session_timeout", 86400)
        st.session_state["_session_timeout"] = int(str(_raw_timeout)) if _raw_timeout else 86400
        st.session_state["_auth_token"] = str(token)
        try:
            st.query_params.clear()
        except Exception:
            pass
        return True
    except Exception:
        pass
    return False


def require_auth():
    _show_login_form = importlib.import_module("auth.ui")._show_login_form

    _run_parent_js(_LOCALSTORAGE_READER_JS)
    has_runtime_auth = bool(st.session_state.get("authenticated") and st.session_state.get("user"))

    restored = False
    if not has_runtime_auth:
        restored = _try_restore_session_from_token()
        if not restored:
            _check_session_expiry()
    else:
        _check_session_expiry()

    if not st.session_state.get("authenticated", False):
        _show_login_form()
        st.stop()
    token = st.session_state.get("_auth_token", "")
    if token:
        timeout_sec = int(str(st.session_state.get("_session_timeout", 86400)))
        _inject_localstorage_token(token, timeout_sec)
    st.markdown(_WAKELOCK_JS, unsafe_allow_html=True)
    return st.session_state["user"]


def logout():
    token = st.session_state.get("_auth_token", "")
    if token:
        try:
            from data.database import delete_session_token

            delete_session_token(str(token))
        except Exception:
            pass
    _clear_localstorage_token()
    _clear_auth_state()
    st.rerun()
