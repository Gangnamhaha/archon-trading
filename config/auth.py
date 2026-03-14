import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_plan_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            expires_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
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
    else:
        # Always ensure admin password is 7777
        salt = secrets.token_hex(16)
        pw_hash = hashlib.pbkdf2_hmac("sha256", "7777".encode(), salt.encode(), 100_000).hex()
        conn.execute(
            "UPDATE users SET password_hash=?, salt=? WHERE username='admin'",
            (pw_hash, salt)
        )
        conn.commit()

    conn.close()


_init_users_table()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def verify_user(username: str, password: str) -> Optional[dict[str, object]]:
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


def is_pro(user: Optional[dict[str, object]] = None) -> bool:
    if user is None:
        user = st.session_state.get("user", {})
    current_user = user or {}
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
        show_upgrade_prompt()
        st.stop()
    return user


def _show_login_form():
    st.markdown("""
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
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# 🏛️ ARCHON")
    st.markdown("### AI 기반 주식 자동매매 플랫폼")

    st.markdown("""
    <div class="archon-landing">
        <h2 style="margin:0 0 0.6rem 0;color:#E2E8F0;">AI가 당신의 투자를 자동화합니다</h2>
        <p style="margin:0;color:#A0AEC0;">전략 수립부터 자동 실행까지, AI가 쉬지 않고 시장을 모니터링합니다.</p>
    </div>
    """, unsafe_allow_html=True)

    stat1, stat2, stat3 = st.columns(3)
    with stat1:
        st.markdown("""
        <div class="archon-card" style="text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:#00D4AA;">13+</div>
            <div style="color:#A0AEC0;">기능 제공</div>
        </div>
        """, unsafe_allow_html=True)
    with stat2:
        st.markdown("""
        <div class="archon-card" style="text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:#00D4AA;">3개</div>
            <div style="color:#A0AEC0;">증권사 연동</div>
        </div>
        """, unsafe_allow_html=True)
    with stat3:
        st.markdown("""
        <div class="archon-card" style="text-align:center;">
            <div style="font-size:1.5rem;font-weight:700;color:#00D4AA;">5개</div>
            <div style="color:#A0AEC0;">동시 오토파일럿</div>
        </div>
        """, unsafe_allow_html=True)

    feature1, feature2, feature3 = st.columns(3)
    with feature1:
        st.markdown("""
        <div class="archon-card">
            <h4 style="margin:0 0 0.35rem 0;color:#E2E8F0;">🤖 AI 오토파일럿</h4>
            <p style="margin:0;color:#A0AEC0;">종목 추천부터 매매까지 완전 자동</p>
        </div>
        """, unsafe_allow_html=True)
    with feature2:
        st.markdown("""
        <div class="archon-card">
            <h4 style="margin:0 0 0.35rem 0;color:#E2E8F0;">📊 고급 분석 도구</h4>
            <p style="margin:0;color:#A0AEC0;">기술적분석, 백테스팅, 리스크분석</p>
        </div>
        """, unsafe_allow_html=True)
    with feature3:
        st.markdown("""
        <div class="archon-card">
            <h4 style="margin:0 0 0.35rem 0;color:#E2E8F0;">💬 AI 채팅</h4>
            <p style="margin:0;color:#A0AEC0;">OpenAI, Claude, Gemini 지원</p>
        </div>
        """, unsafe_allow_html=True)

    price1, price2 = st.columns(2)
    with price1:
        st.markdown("""
        <div class="archon-price-card">
            <h4 style="margin:0 0 0.5rem 0;color:#E2E8F0;">Free</h4>
            <div style="color:#A0AEC0;line-height:1.8;">
                기본 기능 무료<br>
                일봉 데이터<br>
                5개 지표<br>
                포트폴리오 5종목
            </div>
        </div>
        """, unsafe_allow_html=True)
    with price2:
        st.markdown("""
        <div class="archon-price-card pro">
            <h4 style="margin:0 0 0.5rem 0;color:#00D4AA;">Pro 월 99,000원</h4>
            <div style="color:#A0AEC0;line-height:1.8;">
                모든 기능 무제한<br>
                오토파일럿<br>
                AI예측<br>
                종목추천
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="
        background:linear-gradient(90deg, rgba(0,212,170,0.18), rgba(0,212,170,0.05));
        border:1px solid rgba(0,212,170,0.35);
        border-radius:14px;
        padding:1rem;
        margin:1rem 0 1.2rem 0;
        text-align:center;
    ">
        <h3 style="margin:0;color:#00D4AA;">⚡ 지금 시작하세요</h3>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem 0">
        <h1 style="color:#00D4AA;margin:0">Archon</h1>
        <p style="color:#A0AEC0">AI 주식자동매매플랫폼</p>
    </div>""", unsafe_allow_html=True)

    from config.styles import show_share_buttons
    show_share_buttons()
    st.markdown("---")
    st.markdown("### 📧 뉴스레터 구독")
    _nl1, _nl2 = st.columns([3, 1])
    with _nl1:
        _nl_email = st.text_input("이메일", placeholder="your@email.com", key="_nl_email", label_visibility="collapsed")
    with _nl2:
        if st.button("구독", type="primary", use_container_width=True, key="_nl_sub"):
            if _nl_email and "@" in _nl_email:
                from data.database import subscribe_newsletter
                if subscribe_newsletter(_nl_email):
                    st.success("구독 완료!")
                else:
                    st.info("이미 구독 중입니다.")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            agree = st.checkbox("이용약관 및 개인정보처리방침에 동의합니다", key="login_agree")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

            if submitted:
                if not agree:
                    st.warning("약관에 동의해야 로그인할 수 있습니다.")
                elif not username or not password:
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
