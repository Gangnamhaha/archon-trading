import hashlib
import importlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import pyotp
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portfolio.db")
VALID_PLANS = {"free", "plus", "pro"}


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_users_table():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()

    try:
        conn.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.execute("UPDATE users SET plan='pro' WHERE role='admin' AND plan='free'")
    conn.commit()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_plan_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            expires_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if cursor.fetchone()[0] == 0:
        default_pw = os.environ.get("ARCHON_ADMIN_PASSWORD", "7777")
        salt = secrets.token_hex(16)
        pw_hash = hashlib.pbkdf2_hmac("sha256", default_pw.encode(), salt.encode(), 100_000).hex()
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, plan) VALUES (?, ?, ?, ?, ?)",
            ("admin", pw_hash, salt, "admin", "pro"),
        )
        conn.commit()

    conn.close()


_init_users_table()

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300  # 5분


def _init_login_attempts_table():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            username TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0
        )
    """
    )
    conn.commit()
    conn.close()


_init_login_attempts_table()


def _record_login_attempt(username: str, success: bool):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO login_attempts (username, attempted_at, success) VALUES (?, ?, ?)",
        (username, datetime.now().isoformat(), int(success)),
    )
    # 오래된 기록 정리 (24시간 이상)
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    conn.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def _clear_login_attempts(username: str):
    conn = _get_conn()
    conn.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
    conn.commit()
    conn.close()


def get_login_lockout_remaining(username: str) -> int:
    """잠금 남은 시간(초)을 반환. 0이면 잠금 없음."""
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(seconds=LOGIN_LOCKOUT_SECONDS)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) as cnt, MAX(attempted_at) as last_at "
        "FROM login_attempts WHERE username = ? AND attempted_at > ? AND success = 0",
        (username, cutoff),
    ).fetchone()
    conn.close()
    if row is None or row["cnt"] < MAX_LOGIN_ATTEMPTS:
        return 0
    last_at = datetime.fromisoformat(row["last_at"])
    unlock_at = last_at + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
    remaining = (unlock_at - datetime.now()).total_seconds()
    return max(0, int(remaining))


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def verify_user(username: str, password: str) -> Optional[dict[str, object]]:
    lockout = get_login_lockout_remaining(username)
    if lockout > 0:
        return None

    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row is None:
        _record_login_attempt(username, False)
        return None
    pw_hash = _hash_password(password, row["salt"])
    if pw_hash != row["password_hash"]:
        _record_login_attempt(username, False)
        return None
    _clear_login_attempts(username)
    return {"id": row["id"], "username": row["username"], "role": row["role"], "plan": row["plan"]}


def login(username: str, password: str) -> Optional[dict[str, object]]:
    return verify_user(username, password)


def create_user(username: str, password: str, role: str = "user", plan: str = "free") -> bool:
    if role == "admin":
        plan = "pro"
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, plan) VALUES (?, ?, ?, ?, ?)",
            (username, pw_hash, salt, role, plan),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def delete_user(user_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM users WHERE id = ? AND username != 'admin'", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def change_password(user_id: int, new_password: str):
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(new_password, salt)
    conn = _get_conn()
    conn.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (pw_hash, salt, user_id))
    conn.commit()
    conn.close()


def get_all_users() -> pd.DataFrame:
    conn = _get_conn()
    df = pd.read_sql_query("SELECT id, username, role, plan, created_at FROM users ORDER BY id", conn)
    conn.close()
    return df


def update_user_plan(user_id: int, plan: str):
    if plan not in VALID_PLANS:
        raise ValueError(f"Unsupported plan: {plan}")

    conn = _get_conn()
    conn.execute("UPDATE users SET plan=? WHERE id=?", (plan, user_id))
    if plan == "free":
        conn.execute("DELETE FROM user_plan_meta WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    _sync_session_user_plan(user_id, plan)


def _sync_session_user_plan(user_id: int, plan: str):
    session_user = st.session_state.get("user")
    if session_user and session_user.get("id") == user_id:
        session_user["plan"] = plan
        st.session_state["user"] = session_user


def get_plan_expiry(user_id: int) -> Optional[datetime]:
    conn = _get_conn()
    row = conn.execute("SELECT expires_at FROM user_plan_meta WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row is None or not row["expires_at"]:
        return None
    try:
        return datetime.fromisoformat(row["expires_at"])
    except ValueError:
        return None


def grant_pro_days(user_id: int, days: int):
    now = datetime.now()
    current_expiry = get_plan_expiry(user_id)
    base_time = current_expiry if current_expiry and current_expiry > now else now
    new_expiry = base_time + timedelta(days=days)

    conn = _get_conn()
    conn.execute("UPDATE users SET plan='pro' WHERE id=?", (user_id,))
    conn.execute(
        """
        INSERT INTO user_plan_meta (user_id, expires_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            expires_at=excluded.expires_at,
            updated_at=CURRENT_TIMESTAMP
        """,
        (user_id, new_expiry.isoformat()),
    )
    conn.commit()
    conn.close()
    _sync_session_user_plan(user_id, "pro")


def is_admin() -> bool:
    return st.session_state.get("user", {}).get("role") == "admin"


def _resolve_user(user: Optional[dict[str, object]] = None) -> dict[str, object]:
    if user is None:
        user = st.session_state.get("user", {})
    return user or {}


def is_paid(user: Optional[dict[str, object]] = None) -> bool:
    current_user = _resolve_user(user)
    if current_user.get("role") == "admin":
        return True
    return current_user.get("plan") in {"plus", "pro"}


def is_plus(user: Optional[dict[str, object]] = None) -> bool:
    current_user = _resolve_user(user)
    if current_user.get("role") == "admin":
        return False
    return current_user.get("plan") == "plus"


def is_pro(user: Optional[dict[str, object]] = None) -> bool:
    current_user = _resolve_user(user)
    if current_user.get("role") == "admin":
        return True

    if current_user.get("plan") != "pro":
        return False

    user_id = current_user.get("id")
    if user_id is None:
        return True

    if not isinstance(user_id, int):
        return False

    expiry = get_plan_expiry(user_id)
    if expiry and expiry < datetime.now():
        update_user_plan(user_id, "free")
        return False
    return True


def show_upgrade_prompt():
    st.markdown(
        """
    <div style="
        max-width:520px;margin:3rem auto;padding:2.5rem;text-align:center;
        background:rgba(26,31,46,0.85);
        border:1px solid rgba(0,212,170,0.25);
        border-radius:16px;
        backdrop-filter:blur(12px);
        box-shadow:0 8px 32px rgba(0,212,170,0.12);
    ">
        <div style="font-size:3rem;margin-bottom:0.5rem">💎</div>
        <h2 style="color:#00D4AA;margin:0 0 0.5rem 0">Pro 전용 기능</h2>
        <p style="color:#A0AEC0;margin-bottom:1.5rem">
            이 기능은 <b style="color:#00D4AA">Archon Pro</b> 플랜에서만 사용할 수 있습니다.<br>
            업그레이드하고 모든 프리미엄 기능을 잠금 해제하세요.
        </p>
        <div style="
            background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.15);
            border-radius:10px;padding:1rem;margin-bottom:1.5rem;text-align:left;
        ">
            <div style="color:#E2E8F0;font-weight:600;margin-bottom:0.5rem">Pro 플랜 포함 기능:</div>
            <div style="color:#A0AEC0;font-size:0.9rem;line-height:1.8">
                ✅ 백테스팅 엔진<br>
                ✅ AI 가격 예측<br>
                ✅ 리스크 분석 & 몬테카를로<br>
                ✅ AI 종목추천<br>
                ✅ 자동매매 봇<br>
                ✅ 무제한 데이터 분석 (분봉/주봉)<br>
                ✅ 무제한 기술적 지표<br>
                ✅ 무제한 포트폴리오/워치리스트<br>
            </div>
        </div>
        <p style="color:#718096;font-size:0.8rem">
            관리자에게 문의하여 플랜을 업그레이드하세요.
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def show_paid_prompt():
    st.markdown(
        """
    <div style="
        max-width:520px;margin:3rem auto;padding:2.5rem;text-align:center;
        background:rgba(26,31,46,0.85);
        border:1px solid rgba(56,189,248,0.25);
        border-radius:16px;
        backdrop-filter:blur(12px);
        box-shadow:0 8px 32px rgba(56,189,248,0.12);
    ">
        <div style="font-size:3rem;margin-bottom:0.5rem">✨</div>
        <h2 style="color:#38BDF8;margin:0 0 0.5rem 0">Plus 이상 전용 기능</h2>
        <p style="color:#A0AEC0;margin-bottom:1.5rem">
            이 기능은 <b style="color:#38BDF8">Archon Plus</b> 또는 <b style="color:#00D4AA">Pro</b> 플랜에서 사용할 수 있습니다.<br>
            업그레이드하고 고급 분석 기능을 잠금 해제하세요.
        </p>
        <div style="
            background:rgba(56,189,248,0.08);border:1px solid rgba(56,189,248,0.15);
            border-radius:10px;padding:1rem;margin-bottom:1.5rem;text-align:left;
        ">
            <div style="color:#E2E8F0;font-weight:600;margin-bottom:0.5rem">Plus 플랜 포함 기능:</div>
            <div style="color:#A0AEC0;font-size:0.9rem;line-height:1.8">
                ✅ 분봉/주봉/월봉 데이터 분석<br>
                ✅ 무제한 기술적 지표<br>
                ✅ 무제한 포트폴리오<br>
                ✅ 뉴스감성분석<br>
                ✅ 백테스팅 엔진<br>
            </div>
        </div>
        <p style="color:#718096;font-size:0.8rem">
            결제 페이지에서 Plus 또는 Pro 플랜을 선택하세요.
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def require_pro():
    require_auth = importlib.import_module("auth.session").require_auth
    user = require_auth()
    if not is_pro(user):
        show_upgrade_prompt()
        st.stop()
    return user


def require_paid():
    require_auth = importlib.import_module("auth.session").require_auth
    user = require_auth()
    if not is_paid(user):
        show_paid_prompt()
        st.stop()
    return user


# --- 2FA (TOTP) ---

def _init_totp_table():
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_totp (
            user_id INTEGER PRIMARY KEY,
            secret TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


_init_totp_table()


def generate_totp_secret(user_id: int) -> str:
    secret = pyotp.random_base32()
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO admin_totp (user_id, secret, enabled) VALUES (?, ?, 0)",
        (user_id, secret),
    )
    conn.commit()
    conn.close()
    return secret


def enable_totp(user_id: int):
    conn = _get_conn()
    conn.execute("UPDATE admin_totp SET enabled = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def disable_totp(user_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM admin_totp WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_totp_secret(user_id: int) -> Optional[str]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT secret FROM admin_totp WHERE user_id = ? AND enabled = 1", (user_id,)
    ).fetchone()
    conn.close()
    return row["secret"] if row else None


def is_totp_enabled(user_id: int) -> bool:
    return get_totp_secret(user_id) is not None


def verify_totp(user_id: int, code: str) -> bool:
    secret = get_totp_secret(user_id)
    if not secret:
        return True  # 2FA 미설정 시 통과
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_totp_provisioning_uri(user_id: int, username: str) -> Optional[str]:
    conn = _get_conn()
    row = conn.execute("SELECT secret FROM admin_totp WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return pyotp.TOTP(row["secret"]).provisioning_uri(name=username, issuer_name="Archon")
