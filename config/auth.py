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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if cursor.fetchone()[0] == 0:
        salt = secrets.token_hex(16)
        pw_hash = hashlib.pbkdf2_hmac("sha256", "admin123".encode(), salt.encode(), 100_000).hex()
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
            ("admin", pw_hash, salt, "admin")
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
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def create_user(username: str, password: str, role: str = "user") -> bool:
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
            (username, pw_hash, salt, role)
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
    df = pd.read_sql_query("SELECT id, username, role, created_at FROM users ORDER BY id", conn)
    conn.close()
    return df


def is_admin() -> bool:
    return st.session_state.get("user", {}).get("role") == "admin"


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
        login_tab, register_tab = st.tabs(["Login", "Sign Up"])

        with login_tab:
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

        with register_tab:
            with st.form("register_form"):
                reg_username = st.text_input("Username", key="reg_user")
                reg_password = st.text_input("Password", type="password", key="reg_pass")
                reg_password2 = st.text_input("Confirm Password", type="password", key="reg_pass2")
                reg_submitted = st.form_submit_button("Sign Up", type="primary", use_container_width=True)

                if reg_submitted:
                    if not reg_username or not reg_password:
                        st.error("모든 필드를 입력하세요.")
                    elif len(reg_password) < 4:
                        st.error("비밀번호는 4자 이상이어야 합니다.")
                    elif reg_password != reg_password2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    elif create_user(reg_username, reg_password):
                        st.success("회원가입 완료! Login 탭에서 로그인하세요.")
                    else:
                        st.error("이미 존재하는 아이디입니다.")


def require_auth():
    if not st.session_state.get("authenticated", False):
        _show_login_form()
        st.stop()
    return st.session_state["user"]


def logout():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.rerun()
