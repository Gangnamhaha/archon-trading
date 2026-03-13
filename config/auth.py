import sqlite3
import hashlib
import secrets
import os
from typing import Optional
import streamlit as st
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portfolio.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_users_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    try:
        conn.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.execute("UPDATE users SET plan='pro' WHERE role='admin' AND plan='free'")
    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if cursor.fetchone()[0] == 0:
        salt = secrets.token_hex(16)
        pw_hash = hashlib.pbkdf2_hmac("sha256", "7777".encode(), salt.encode(), 100_000).hex()
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, plan) VALUES (?, ?, ?, ?, ?)",
            ("admin", pw_hash, salt, "admin", "pro")
        )
        conn.commit()

    conn.close()


_init_users_table()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def verify_user(username: str, password: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row is None:
        return None
    pw_hash = _hash_password(password, row["salt"])
    if pw_hash != row["password_hash"]:
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"], "plan": row["plan"]}


def create_user(username: str, password: str, role: str = "user", plan: str = "free") -> bool:
    if role == "admin":
        plan = "pro"
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, plan) VALUES (?, ?, ?, ?, ?)",
            (username, pw_hash, salt, role, plan)
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
    conn = _get_conn()
    conn.execute("UPDATE users SET plan=? WHERE id=?", (plan, user_id))
    conn.commit()
    conn.close()


def is_admin() -> bool:
    return st.session_state.get("user", {}).get("role") == "admin"


def is_pro(user: Optional[dict] = None) -> bool:
    if user is None:
        user = st.session_state.get("user", {})
    return user.get("plan") == "pro" or user.get("role") == "admin"


def show_upgrade_prompt():
    st.markdown("""
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
    """, unsafe_allow_html=True)


def require_pro():
    user = require_auth()
    if not is_pro(user):
        from config.styles import inject_pro_css
        inject_pro_css()
        show_upgrade_prompt()
        st.stop()
    return user


def _show_login_form():
    from config.styles import inject_pro_css
    inject_pro_css()

    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem 0">
        <h1 style="color:#00D4AA;margin:0">Archon</h1>
        <p style="color:#A0AEC0">AI 주식자동매매플랫폼</p>
    </div>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("모든 필드를 입력하세요.")
                else:
                    user = verify_user(username, password)
                    if user:
                        st.session_state["authenticated"] = True
                        st.session_state["user"] = user
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 틀렸습니다.")


def require_auth():
    if not st.session_state.get("authenticated", False):
        _show_login_form()
        st.stop()
    return st.session_state["user"]


def logout():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.rerun()
