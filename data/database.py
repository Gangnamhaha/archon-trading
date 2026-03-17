"""
SQLite 데이터베이스 모듈
- 포트폴리오 데이터 관리
- 거래 이력 관리
"""
import sqlite3
import os
import random
import string
import base64
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import time as _time

_rate_limits: dict[str, list[float]] = {}

def _check_rate_limit(key: str, max_calls: int = 10, window: int = 60) -> bool:
    now = _time.time()
    if key not in _rate_limits:
        _rate_limits[key] = []
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= max_calls:
        return False
    _rate_limits[key].append(now)
    return True

DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")

_ENCRYPT_KEY = hashlib.sha256(
    os.environ.get("ARCHON_SECRET", "archon-default-key-change-me").encode()
).digest()

_SENSITIVE_KEYS = ("api_key", "app_key", "app_secret", "secret_key")


def _xor_encrypt(data: str) -> str:
    raw = data.encode("utf-8")
    encrypted = bytes(b ^ _ENCRYPT_KEY[i % len(_ENCRYPT_KEY)] for i, b in enumerate(raw))
    return base64.b64encode(encrypted).decode("ascii")


def _xor_decrypt(data: str) -> str:
    encrypted = base64.b64decode(data.encode("ascii"))
    decrypted = bytes(b ^ _ENCRYPT_KEY[i % len(_ENCRYPT_KEY)] for i, b in enumerate(encrypted))
    return decrypted.decode("utf-8")


def _is_sensitive(key: str) -> bool:
    return any(s in key.lower() for s in _SENSITIVE_KEYS)


def get_connection():
    """DB 연결 생성"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 초기화"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'KR',
            name TEXT,
            buy_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            buy_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'KR',
            action TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            strategy TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'KR',
            name TEXT,
            username TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, username)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            setting_key TEXT NOT NULL,
            setting_value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, setting_key)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            chat_type TEXT NOT NULL DEFAULT 'general',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            owner_username TEXT NOT NULL,
            used_by TEXT,
            reward_type TEXT DEFAULT 'pro_7days',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            used_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_plan_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            expires_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS newsletter_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            slot_idx INTEGER NOT NULL DEFAULT 0,
            market TEXT NOT NULL DEFAULT 'KOSPI',
            mode TEXT NOT NULL DEFAULT '일반 추천',
            capital INTEGER NOT NULL DEFAULT 1000000,
            max_stocks INTEGER NOT NULL DEFAULT 5,
            max_per INTEGER NOT NULL DEFAULT 20,
            stop_loss REAL NOT NULL DEFAULT 5.0,
            take_profit REAL NOT NULL DEFAULT 15.0,
            daily_limit REAL NOT NULL DEFAULT 5.0,
            usdkrw REAL NOT NULL DEFAULT 1350.0,
            status TEXT NOT NULL DEFAULT 'stopped',
            last_run_at TEXT,
            next_run_at TEXT,
            holdings TEXT NOT NULL DEFAULT '{}',
            daily_pnl REAL NOT NULL DEFAULT 0.0,
            run_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, slot_idx)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            slot_idx INTEGER NOT NULL DEFAULT 0,
            log_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ap_jobs_user ON autopilot_jobs(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ap_logs_user ON autopilot_logs(username, created_at)")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            plan TEXT NOT NULL,
            session_timeout INTEGER NOT NULL DEFAULT 86400,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )
    """)

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_tokens_token ON session_tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_tokens_expires ON session_tokens(expires_at)")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '접수',
            admin_note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marketing_automation_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            run_type TEXT NOT NULL DEFAULT 'SNS 포스트',
            market TEXT NOT NULL DEFAULT 'KOSPI',
            platform TEXT NOT NULL DEFAULT '트위터 (280자)',
            publish_channel TEXT NOT NULL DEFAULT '일반 웹훅',
            interval_minutes INTEGER NOT NULL DEFAULT 120,
            webhook_url TEXT,
            publish_notice INTEGER NOT NULL DEFAULT 0,
            notify_on_failure INTEGER NOT NULL DEFAULT 1,
            alert_email TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            last_run_at TEXT,
            next_run_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        cursor.execute("ALTER TABLE marketing_automation_jobs ADD COLUMN run_type TEXT NOT NULL DEFAULT 'SNS 포스트'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketing_automation_jobs ADD COLUMN publish_channel TEXT NOT NULL DEFAULT '일반 웹훅'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketing_automation_jobs ADD COLUMN notify_on_failure INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE marketing_automation_jobs ADD COLUMN alert_email TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marketing_automation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            content_preview TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            username TEXT NOT NULL,
            plan_type TEXT,
            amount INTEGER,
            currency TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider, payment_id)
        )
    """)


    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user ON chat_history(username, chat_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_user ON activity_log(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_history_ticker ON trade_history(ticker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_ticker ON portfolio(ticker)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_owner ON referral_codes(owner_username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notices_created ON notices(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_newsletter_email ON newsletter_subscribers(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_receipts_user ON payment_receipts(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mkt_logs_user ON marketing_automation_logs(username, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inquiries_status ON customer_inquiries(status, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inquiries_user ON customer_inquiries(username, created_at)")

    conn.commit()
    conn.close()


# === 사용자 설정 저장/로드 ===

def save_user_setting(username: str, key: str, value: str):
    init_db()
    stored = _xor_encrypt(value) if _is_sensitive(key) and value else value
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO user_settings (username, setting_key, setting_value, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (username, key, stored, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load_user_setting(username: str, key: str, default: Optional[str] = None):
    init_db()
    conn = get_connection()
    cursor = conn.execute(
        "SELECT setting_value FROM user_settings WHERE username = ? AND setting_key = ?",
        (username, key)
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return default
    raw = row["setting_value"]
    if _is_sensitive(key) and raw:
        try:
            return _xor_decrypt(raw)
        except Exception:
            return raw
    return raw


def load_all_user_settings(username: str) -> dict[str, str]:
    init_db()
    conn = get_connection()
    cursor = conn.execute(
        "SELECT setting_key, setting_value FROM user_settings WHERE username = ?",
        (username,)
    )
    settings = {row["setting_key"]: row["setting_value"] for row in cursor.fetchall()}
    conn.close()
    return settings


# === 채팅 이력 저장/로드 ===

def save_chat_message(username: str, chat_type: str, role: str, content: str):
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_history (username, chat_type, role, content) VALUES (?, ?, ?, ?)",
        (username, chat_type, role, content)
    )
    conn.commit()
    conn.close()


def load_chat_history(username: str, chat_type: str = "general", limit: int = 100) -> list[dict[str, str]]:
    init_db()
    conn = get_connection()
    cursor = conn.execute(
        "SELECT role, content FROM chat_history WHERE username = ? AND chat_type = ? "
        "ORDER BY id DESC LIMIT ?",
        (username, chat_type, limit)
    )
    messages = [{"role": row["role"], "content": row["content"]} for row in cursor.fetchall()]
    conn.close()
    messages.reverse()
    return messages


def clear_chat_history(username: str, chat_type: str = "general"):
    conn = get_connection()
    conn.execute(
        "DELETE FROM chat_history WHERE username = ? AND chat_type = ?",
        (username, chat_type)
    )
    conn.commit()
    conn.close()


# === 활동 로그 ===

def log_activity(username: str, action: str, detail: Optional[str] = None):
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_log (username, action, detail) VALUES (?, ?, ?)",
        (username, action, detail)
    )
    conn.commit()
    conn.close()


def get_activity_log(username: str, limit: int = 50) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT action, detail, created_at FROM activity_log WHERE username = ? "
        "ORDER BY id DESC LIMIT ?",
        conn, params=[username, limit]
    )
    conn.close()
    return df


def get_all_activity_logs(limit: int = 100) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT username, action, detail, created_at FROM activity_log ORDER BY id DESC LIMIT ?",
        conn, params=[limit]
    )
    conn.close()
    return df


def _create_referral_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(8))


def _grant_pro_reward(conn, username: str, days: int):
    user_row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if user_row is None:
        return False

    user_id = int(user_row["id"])
    now = datetime.now()
    expiry_row = conn.execute(
        "SELECT expires_at FROM user_plan_meta WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    base_time = now
    if expiry_row and expiry_row["expires_at"]:
        try:
            current_expiry = datetime.fromisoformat(expiry_row["expires_at"])
            if current_expiry > now:
                base_time = current_expiry
        except ValueError:
            base_time = now

    new_expiry = (base_time + timedelta(days=days)).isoformat()

    conn.execute("UPDATE users SET plan='pro' WHERE id = ?", (user_id,))
    conn.execute(
        """
        INSERT INTO user_plan_meta (user_id, expires_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            expires_at=excluded.expires_at,
            updated_at=CURRENT_TIMESTAMP
        """,
        (user_id, new_expiry),
    )
    return True


def generate_referral_code(username: str) -> str:
    init_db()
    conn = get_connection()
    try:
        while True:
            code = _create_referral_code()
            exists = conn.execute("SELECT id FROM referral_codes WHERE code = ?", (code,)).fetchone()
            if exists is None:
                conn.execute(
                    "INSERT INTO referral_codes (code, owner_username) VALUES (?, ?)",
                    (code, username),
                )
                conn.commit()
                return code
    finally:
        conn.close()


def get_referral_code(username: str) -> str:
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT code FROM referral_codes WHERE owner_username = ? AND used_by IS NULL ORDER BY id DESC LIMIT 1",
        (username,),
    ).fetchone()
    conn.close()
    if row:
        return row["code"]
    return generate_referral_code(username)


def use_referral_code(code: str, new_username: str):
    init_db()
    normalized_code = (code or "").strip().upper()
    if not normalized_code:
        return False, "추천인 코드를 입력하세요."

    conn = get_connection()
    try:
        referral = conn.execute(
            "SELECT id, owner_username FROM referral_codes WHERE code = ? AND used_by IS NULL",
            (normalized_code,),
        ).fetchone()
        if referral is None:
            return False, "유효하지 않거나 이미 사용된 코드입니다."

        owner_username = referral["owner_username"]
        if owner_username == new_username:
            return False, "본인 코드는 사용할 수 없습니다."

        already_used = conn.execute(
            "SELECT id FROM referral_codes WHERE used_by = ? LIMIT 1",
            (new_username,),
        ).fetchone()
        if already_used:
            return False, "이미 추천인 코드를 사용했습니다."

        owner_exists = conn.execute("SELECT id FROM users WHERE username = ?", (owner_username,)).fetchone()
        new_user_exists = conn.execute("SELECT id FROM users WHERE username = ?", (new_username,)).fetchone()
        if owner_exists is None or new_user_exists is None:
            return False, "사용자 정보를 찾을 수 없습니다."

        used_at = datetime.now().isoformat()
        result = conn.execute(
            "UPDATE referral_codes SET used_by = ?, used_at = ? WHERE id = ? AND used_by IS NULL",
            (new_username, used_at, referral["id"]),
        )
        if result.rowcount == 0:
            return False, "코드 사용 처리 중 오류가 발생했습니다. 다시 시도해 주세요."

        owner_rewarded = _grant_pro_reward(conn, owner_username, 7)
        new_rewarded = _grant_pro_reward(conn, new_username, 7)
        if not owner_rewarded or not new_rewarded:
            conn.rollback()
            return False, "리워드 처리 중 오류가 발생했습니다. 다시 시도해 주세요."

        conn.commit()
    finally:
        conn.close()

    return True, "추천인 리워드가 적용되었습니다! 양쪽 모두 Pro 7일이 지급되었습니다."


def get_referral_stats(username: str) -> int:
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM referral_codes WHERE owner_username = ? AND used_by IS NOT NULL",
        (username,),
    ).fetchone()
    conn.close()
    return int(row["cnt"] if row else 0)


# === 워치리스트 ===

def add_watchlist(ticker: str, market: str, name: str, username: str):
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, market, name, username) VALUES (?, ?, ?, ?)",
            (ticker, market, name, username)
        )
        conn.commit()
    finally:
        conn.close()


def remove_watchlist(ticker: str, username: str):
    conn = get_connection()
    conn.execute("DELETE FROM watchlist WHERE ticker = ? AND username = ?", (ticker, username))
    conn.commit()
    conn.close()


def get_watchlist(username: str) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM watchlist WHERE username = ? ORDER BY created_at DESC", conn, params=[username]
    )
    conn.close()
    return df


# === 포트폴리오 CRUD ===

def add_stock(ticker: str, market: str, name: str, buy_price: float, quantity: int, buy_date: Optional[str] = None):
    """포트폴리오에 종목 추가"""
    if buy_date is None:
        buy_date = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute(
        "INSERT INTO portfolio (ticker, market, name, buy_price, quantity, buy_date) VALUES (?, ?, ?, ?, ?, ?)",
        (ticker, market, name, buy_price, quantity, buy_date)
    )
    conn.commit()
    conn.close()


def remove_stock(stock_id: int):
    """포트폴리오에서 종목 삭제"""
    conn = get_connection()
    conn.execute("DELETE FROM portfolio WHERE id = ?", (stock_id,))
    conn.commit()
    conn.close()


def get_portfolio() -> pd.DataFrame:
    """전체 포트폴리오 조회"""
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM portfolio ORDER BY buy_date DESC", conn)
    conn.close()
    return df


def update_stock(stock_id: int, buy_price: Optional[float] = None, quantity: Optional[int] = None):
    """포트폴리오 종목 수정"""
    conn = get_connection()
    if buy_price is not None:
        conn.execute("UPDATE portfolio SET buy_price = ? WHERE id = ?", (buy_price, stock_id))
    if quantity is not None:
        conn.execute("UPDATE portfolio SET quantity = ? WHERE id = ?", (quantity, stock_id))
    conn.commit()
    conn.close()


# === 거래 이력 ===

def add_trade(ticker: str, market: str, action: str, price: float, quantity: int, strategy: Optional[str] = None):
    """거래 이력 추가"""
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO trade_history (ticker, market, action, price, quantity, strategy) VALUES (?, ?, ?, ?, ?, ?)",
        (ticker, market, action, price, quantity, strategy)
    )
    conn.commit()
    conn.close()


def get_trades(ticker: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
    """거래 이력 조회"""
    init_db()
    conn = get_connection()
    if ticker:
        df = pd.read_sql_query(
            "SELECT * FROM trade_history WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?",
            conn, params=[ticker, limit]
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM trade_history ORDER BY timestamp DESC LIMIT ?",
            conn, params=[limit]
        )
    conn.close()
    return df


def subscribe_newsletter(email: str) -> bool:
    init_db()
    conn = get_connection()
    try:
        conn.execute("INSERT INTO newsletter_subscribers (email) VALUES (?)", (email,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_newsletter_subscribers() -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT email, subscribed_at FROM newsletter_subscribers ORDER BY id DESC", conn)
    conn.close()
    return df


def add_notice(title: str, content: str, author: str):
    init_db()
    conn = get_connection()
    conn.execute("INSERT INTO notices (title, content, author) VALUES (?, ?, ?)", (title, content, author))
    conn.commit()
    conn.close()


def upsert_marketing_automation_job(
    username: str,
    run_type: str,
    market: str,
    platform: str,
    publish_channel: str,
    interval_minutes: int,
    webhook_url: Optional[str],
    publish_notice: bool,
    notify_on_failure: bool,
    alert_email: Optional[str],
    is_active: bool,
):
    init_db()
    now = datetime.now()
    next_run = now + timedelta(minutes=max(1, int(interval_minutes)))
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO marketing_automation_jobs
        (username, run_type, market, platform, publish_channel, interval_minutes, webhook_url, publish_notice,
         notify_on_failure, alert_email, is_active, next_run_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            run_type=excluded.run_type,
            market=excluded.market,
            platform=excluded.platform,
            publish_channel=excluded.publish_channel,
            interval_minutes=excluded.interval_minutes,
            webhook_url=excluded.webhook_url,
            publish_notice=excluded.publish_notice,
            notify_on_failure=excluded.notify_on_failure,
            alert_email=excluded.alert_email,
            is_active=excluded.is_active,
            next_run_at=CASE WHEN excluded.is_active=1 THEN excluded.next_run_at ELSE NULL END,
            updated_at=excluded.updated_at
        """,
        (
            username,
            run_type,
            market,
            platform,
            publish_channel,
            int(interval_minutes),
            webhook_url or None,
            1 if publish_notice else 0,
            1 if notify_on_failure else 0,
            alert_email or None,
            1 if is_active else 0,
            next_run.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_marketing_automation_job(username: str) -> Optional[dict[str, object]]:
    init_db()
    conn = get_connection()
    row = conn.execute(
        """
        SELECT username, run_type, market, platform, publish_channel, interval_minutes, webhook_url,
               publish_notice, notify_on_failure, alert_email,
               is_active, last_run_at, next_run_at, updated_at
        FROM marketing_automation_jobs
        WHERE username=?
        """,
        (username,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "username": row["username"],
        "run_type": row["run_type"],
        "market": row["market"],
        "platform": row["platform"],
        "publish_channel": row["publish_channel"],
        "interval_minutes": int(row["interval_minutes"]),
        "webhook_url": row["webhook_url"] or "",
        "publish_notice": bool(row["publish_notice"]),
        "notify_on_failure": bool(row["notify_on_failure"]),
        "alert_email": row["alert_email"] or "",
        "is_active": bool(row["is_active"]),
        "last_run_at": row["last_run_at"],
        "next_run_at": row["next_run_at"],
        "updated_at": row["updated_at"],
    }


def mark_marketing_automation_run(username: str):
    init_db()
    now = datetime.now()
    conn = get_connection()
    row = conn.execute(
        "SELECT interval_minutes, is_active FROM marketing_automation_jobs WHERE username=?",
        (username,),
    ).fetchone()
    if row is None:
        conn.close()
        return
    next_run = None
    if int(row["is_active"]) == 1:
        next_run = (now + timedelta(minutes=max(1, int(row["interval_minutes"]))))
    conn.execute(
        """
        UPDATE marketing_automation_jobs
        SET last_run_at=?, next_run_at=?, updated_at=?
        WHERE username=?
        """,
        (now.isoformat(), next_run.isoformat() if next_run else None, now.isoformat(), username),
    )
    conn.commit()
    conn.close()


def is_marketing_automation_due(username: str) -> bool:
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT is_active, next_run_at FROM marketing_automation_jobs WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    if row is None or int(row["is_active"]) != 1:
        return False
    next_run_at = row["next_run_at"]
    if not next_run_at:
        return True
    try:
        return datetime.now() >= datetime.fromisoformat(next_run_at)
    except ValueError:
        return True


def add_marketing_automation_log(
    username: str,
    run_type: str,
    status: str,
    message: str,
    content_preview: Optional[str] = None,
):
    init_db()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO marketing_automation_logs (username, run_type, status, message, content_preview)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, run_type, status, message, content_preview),
    )
    conn.commit()
    conn.close()


def get_marketing_automation_logs(username: str, limit: int = 20) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT run_type, status, message, content_preview, created_at
        FROM marketing_automation_logs
        WHERE username=?
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=[username, limit],
    )
    conn.close()
    return df


def get_notices(limit: int = 20) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM notices ORDER BY id DESC LIMIT ?", conn, params=[limit])
    conn.close()
    return df


def add_customer_inquiry(username: str, category: str, title: str, content: str):
    init_db()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO customer_inquiries (username, category, title, content, status, updated_at)
        VALUES (?, ?, ?, ?, '접수', ?)
        """,
        (username, category, title, content, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_customer_inquiries(status: Optional[str] = None, limit: int = 200) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    if status and status != "전체":
        df = pd.read_sql_query(
            """
            SELECT id, username, category, title, content, status, admin_note, created_at, updated_at
            FROM customer_inquiries
            WHERE status = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=[status, limit],
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT id, username, category, title, content, status, admin_note, created_at, updated_at
            FROM customer_inquiries
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=[limit],
        )
    conn.close()
    return df


def update_customer_inquiry(inquiry_id: int, status: str, admin_note: str = ""):
    init_db()
    conn = get_connection()
    conn.execute(
        """
        UPDATE customer_inquiries
        SET status = ?, admin_note = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, admin_note, datetime.now().isoformat(), inquiry_id),
    )
    conn.commit()
    conn.close()


def record_payment_receipt(
    provider: str,
    payment_id: str,
    username: str,
    plan_type: Optional[str] = None,
    amount: Optional[int] = None,
    currency: Optional[str] = None,
) -> bool:
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO payment_receipts (provider, payment_id, username, plan_type, amount, currency)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (provider, payment_id, username, plan_type, amount, currency),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def apply_verified_payment(
    provider: str,
    payment_id: str,
    username: str,
    plan_type: Optional[str] = None,
    amount: Optional[int] = None,
    currency: Optional[str] = None,
) -> str:
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO payment_receipts (provider, payment_id, username, plan_type, amount, currency)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (provider, payment_id, username, plan_type, amount, currency),
        )
        updated = conn.execute("UPDATE users SET plan='pro' WHERE username=?", (username,)).rowcount
        if updated == 0:
            conn.rollback()
            return "user_not_found"
        conn.commit()
        return "applied"
    except sqlite3.IntegrityError:
        conn.rollback()
        return "duplicate"
    except Exception:
        conn.rollback()
        return "error"
    finally:
        conn.close()


def create_session_token(
    username: str,
    user_id: int,
    role: str,
    plan: str,
    session_timeout: int = 86400,
    max_sessions: int = 2,
) -> str:
    import secrets as _secrets
    init_db()
    token = _secrets.token_urlsafe(48)
    now = datetime.now()
    if session_timeout > 0:
        expires = now + timedelta(seconds=session_timeout)
    else:
        expires = now + timedelta(days=365 * 10)
    conn = get_connection()
    now_iso = now.isoformat()
    if max_sessions > 0:
        active_count_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM session_tokens WHERE username=? AND expires_at >= ?",
            (username, now_iso),
        ).fetchone()
        active_count = int(active_count_row["cnt"]) if active_count_row is not None else 0
        overflow = active_count - max_sessions + 1
        if overflow > 0:
            conn.execute(
                "DELETE FROM session_tokens WHERE id IN ("
                "SELECT id FROM session_tokens "
                "WHERE username=? AND expires_at >= ? "
                "ORDER BY datetime(created_at) ASC, id ASC "
                "LIMIT ?"
                ")",
                (username, now_iso, overflow),
            )
    conn.execute(
        """
        INSERT INTO session_tokens (token, username, user_id, role, plan, session_timeout, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (token, username, user_id, role, plan, session_timeout, expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def validate_session_token(token: str) -> Optional[dict[str, object]]:
    if not token:
        return None
    init_db()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM session_tokens WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    try:
        expires = datetime.fromisoformat(str(row["expires_at"]))
    except ValueError:
        return None
    if datetime.now() > expires:
        delete_session_token(token)
        return None
    return {
        "id": int(row["user_id"]),
        "username": str(row["username"]),
        "role": str(row["role"]),
        "plan": str(row["plan"]),
        "session_timeout": int(row["session_timeout"]),
    }


def delete_session_token(token: str):
    if not token:
        return
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM session_tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def cleanup_expired_session_tokens():
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM session_tokens WHERE expires_at < ?", (datetime.now().isoformat(),))
    conn.commit()
    conn.close()


def upsert_autopilot_job(
    username: str,
    slot_idx: int,
    market: str,
    mode: str,
    capital: int,
    max_stocks: int,
    max_per: int,
    stop_loss: float,
    take_profit: float,
    daily_limit: float,
    usdkrw: float = 1350.0,
    status: str = "running",
) -> None:
    init_db()
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO autopilot_jobs
            (username, slot_idx, market, mode, capital, max_stocks, max_per,
             stop_loss, take_profit, daily_limit, usdkrw, status, updated_at,
             holdings, daily_pnl, run_count, next_run_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', 0.0, 0, ?)
        ON CONFLICT(username, slot_idx) DO UPDATE SET
            market=excluded.market, mode=excluded.mode, capital=excluded.capital,
            max_stocks=excluded.max_stocks, max_per=excluded.max_per,
            stop_loss=excluded.stop_loss, take_profit=excluded.take_profit,
            daily_limit=excluded.daily_limit, usdkrw=excluded.usdkrw,
            status=excluded.status, updated_at=excluded.updated_at,
            next_run_at=CASE WHEN excluded.status='running' THEN excluded.next_run_at ELSE NULL END
        """,
        (username, slot_idx, market, mode, capital, max_stocks, max_per,
         stop_loss, take_profit, daily_limit, usdkrw, status, now, now),
    )
    conn.commit()
    conn.close()


def stop_autopilot_job(username: str, slot_idx: int) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        "UPDATE autopilot_jobs SET status='stopped', updated_at=? WHERE username=? AND slot_idx=?",
        (datetime.now().isoformat(), username, slot_idx),
    )
    conn.commit()
    conn.close()


def get_autopilot_jobs(username: str) -> list[dict[str, object]]:
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM autopilot_jobs WHERE username=? ORDER BY slot_idx",
        (username,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_autopilot_job_state(
    username: str,
    slot_idx: int,
    holdings: str,
    daily_pnl: float,
    run_count: int,
    next_run_at: str,
) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        """
        UPDATE autopilot_jobs SET
            holdings=?, daily_pnl=?, run_count=?, next_run_at=?,
            last_run_at=?, updated_at=?
        WHERE username=? AND slot_idx=?
        """,
        (holdings, daily_pnl, run_count,
         next_run_at, datetime.now().isoformat(), datetime.now().isoformat(),
         username, slot_idx),
    )
    conn.commit()
    conn.close()


def add_autopilot_log(username: str, slot_idx: int, log_type: str, message: str) -> None:
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO autopilot_logs (username, slot_idx, log_type, message) VALUES (?, ?, ?, ?)",
        (username, slot_idx, log_type, message),
    )
    conn.execute(
        "DELETE FROM autopilot_logs WHERE username=? AND slot_idx=? AND id NOT IN "
        "(SELECT id FROM autopilot_logs WHERE username=? AND slot_idx=? ORDER BY id DESC LIMIT 100)",
        (username, slot_idx, username, slot_idx),
    )
    conn.commit()
    conn.close()


def get_autopilot_logs(username: str, slot_idx: int, limit: int = 50) -> list[str]:
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT message FROM autopilot_logs WHERE username=? AND slot_idx=? ORDER BY id DESC LIMIT ?",
        (username, slot_idx, limit),
    ).fetchall()
    conn.close()
    return [str(r["message"]) for r in reversed(rows)]


# 모듈 임포트 시 DB 초기화
init_db()
