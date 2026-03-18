import importlib

import streamlit as st

_core = importlib.import_module("auth.core")
_session = importlib.import_module("auth.session")
_ui = importlib.import_module("auth.ui")

DB_PATH = _core.DB_PATH
VALID_PLANS = _core.VALID_PLANS
_SESSION_TIMEOUT_OPTIONS = _session._SESSION_TIMEOUT_OPTIONS
_WAKELOCK_JS = _session._WAKELOCK_JS
_LOCALSTORAGE_READER_JS = _session._LOCALSTORAGE_READER_JS
_show_login_form = _ui._show_login_form


def _sync_runtime_state() -> None:
    setattr(_core, "DB_PATH", DB_PATH)
    setattr(_core, "st", st)
    setattr(_session, "st", st)
    setattr(_ui, "st", st)
    setattr(_ui, "_show_login_form", _show_login_form)


def _get_conn():
    _sync_runtime_state()
    return _core._get_conn()


def _init_users_table():
    _sync_runtime_state()
    return _core._init_users_table()


def _hash_password(password: str, salt: str) -> str:
    return _core._hash_password(password, salt)


def verify_user(username: str, password: str):
    _sync_runtime_state()
    return _core.verify_user(username, password)


def login(username: str, password: str):
    _sync_runtime_state()
    return _core.login(username, password)


def create_user(username: str, password: str, role: str = "user", plan: str = "free") -> bool:
    _sync_runtime_state()
    return _core.create_user(username, password, role=role, plan=plan)


def delete_user(user_id: int) -> bool:
    _sync_runtime_state()
    return _core.delete_user(user_id)


def change_password(user_id: int, new_password: str):
    _sync_runtime_state()
    return _core.change_password(user_id, new_password)


def get_all_users():
    _sync_runtime_state()
    return _core.get_all_users()


def update_user_plan(user_id: int, plan: str):
    _sync_runtime_state()
    return _core.update_user_plan(user_id, plan)


def _sync_session_user_plan(user_id: int, plan: str):
    _sync_runtime_state()
    return _core._sync_session_user_plan(user_id, plan)


def get_plan_expiry(user_id: int):
    _sync_runtime_state()
    return _core.get_plan_expiry(user_id)


def grant_pro_days(user_id: int, days: int):
    _sync_runtime_state()
    return _core.grant_pro_days(user_id, days)


def is_admin() -> bool:
    _sync_runtime_state()
    return _core.is_admin()


def _resolve_user(user=None):
    _sync_runtime_state()
    return _core._resolve_user(user)


def is_paid(user=None) -> bool:
    _sync_runtime_state()
    return _core.is_paid(user)


def is_plus(user=None) -> bool:
    _sync_runtime_state()
    return _core.is_plus(user)


def is_pro(user=None) -> bool:
    _sync_runtime_state()
    return _core.is_pro(user)


def show_upgrade_prompt():
    _sync_runtime_state()
    return _core.show_upgrade_prompt()


def show_paid_prompt():
    _sync_runtime_state()
    return _core.show_paid_prompt()


def require_pro():
    _sync_runtime_state()
    return _core.require_pro()


def require_paid():
    _sync_runtime_state()
    return _core.require_paid()


def _get_request_headers() -> dict[str, str]:
    _sync_runtime_state()
    return _session._get_request_headers()


def _infer_client_meta() -> tuple[str, str, str]:
    _sync_runtime_state()
    return _session._infer_client_meta()


def _clear_auth_state():
    _sync_runtime_state()
    return _session._clear_auth_state()


def _check_session_expiry():
    _sync_runtime_state()
    return _session._check_session_expiry()


def _run_parent_js(js_body: str) -> None:
    _sync_runtime_state()
    return _session._run_parent_js(js_body)


def _inject_localstorage_token(token: str, max_age_sec: int = 86400):
    _sync_runtime_state()
    return _session._inject_localstorage_token(token, max_age_sec=max_age_sec)


def _clear_localstorage_token():
    _sync_runtime_state()
    return _session._clear_localstorage_token()


def _try_restore_session_from_token():
    _sync_runtime_state()
    return _session._try_restore_session_from_token()


def require_auth():
    _sync_runtime_state()
    return _session.require_auth()


def logout():
    _sync_runtime_state()
    return _session.logout()


__all__ = [
    "DB_PATH",
    "VALID_PLANS",
    "_get_conn",
    "_init_users_table",
    "_hash_password",
    "verify_user",
    "login",
    "create_user",
    "delete_user",
    "change_password",
    "get_all_users",
    "update_user_plan",
    "_sync_session_user_plan",
    "get_plan_expiry",
    "grant_pro_days",
    "is_admin",
    "_resolve_user",
    "is_paid",
    "is_plus",
    "is_pro",
    "show_upgrade_prompt",
    "show_paid_prompt",
    "require_pro",
    "require_paid",
    "_show_login_form",
    "_SESSION_TIMEOUT_OPTIONS",
    "_get_request_headers",
    "_infer_client_meta",
    "_clear_auth_state",
    "_check_session_expiry",
    "_WAKELOCK_JS",
    "_LOCALSTORAGE_READER_JS",
    "_run_parent_js",
    "_inject_localstorage_token",
    "_clear_localstorage_token",
    "_try_restore_session_from_token",
    "require_auth",
    "logout",
]
