import sqlite3
import hashlib
import secrets
import os
from datetime import datetime, timedelta
from typing import Optional
import streamlit as st
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portfolio.db")
VALID_PLANS = {"free", "plus", "pro"}


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
    """Return True for Pro-only access; shared paid access should use is_paid()."""
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


def show_paid_prompt():
    st.markdown("""
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
    """, unsafe_allow_html=True)


def require_pro():
    user = require_auth()
    if not is_pro(user):
        show_upgrade_prompt()
        st.stop()
    return user


def require_paid():
    user = require_auth()
    if not is_paid(user):
        show_paid_prompt()
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
        .archon-price-card.plus {
            border: 1px solid rgba(56, 189, 248, 0.45);
            box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.16) inset;
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

    price1, price2, price3 = st.columns(3)
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
        <div class="archon-price-card plus">
            <h4 style="margin:0 0 0.5rem 0;color:#38BDF8;">Plus 월 49,000원</h4>
            <div style="color:#A0AEC0;line-height:1.8;">
                분봉/주봉/월봉<br>
                지표 무제한<br>
                포트폴리오 무제한<br>
                뉴스감성분석<br>
                백테스팅
            </div>
        </div>
        """, unsafe_allow_html=True)
    with price3:
        st.markdown("""
        <div class="archon-price-card pro">
            <h4 style="margin:0 0 0.5rem 0;color:#00D4AA;">Pro 월 99,000원</h4>
            <div style="color:#A0AEC0;line-height:1.8;">
                Plus 전체 포함<br>
                오토파일럿<br>
                AI예측<br>
                종목추천<br>
                마케팅도구 / US 자동매매
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
                            st.session_state["authenticated"] = True
                            st.session_state["user"] = user
                            st.session_state["_login_time"] = datetime.now()
                            st.session_state["_session_timeout"] = _SESSION_TIMEOUT_OPTIONS[session_label]
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


_SESSION_TIMEOUT_OPTIONS = {
    "1시간": 3600,
    "6시간": 21600,
    "24시간": 86400,
    "7일": 604800,
    "무제한": 0,
}


def _check_session_expiry():
    timeout = st.session_state.get("_session_timeout", 86400)
    if timeout == 0:
        return
    login_time = st.session_state.get("_login_time")
    if login_time:
        elapsed = (datetime.now() - login_time).total_seconds()
        if elapsed > timeout:
            st.session_state.clear()
            st.warning("세션이 만료되었습니다. 다시 로그인해주세요.")
            st.rerun()


def require_auth():
    _check_session_expiry()
    if not st.session_state.get("authenticated", False):
        _show_login_form()
        st.stop()
    return st.session_state["user"]


def logout():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.rerun()
