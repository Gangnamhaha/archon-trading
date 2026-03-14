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


def get_notices(limit: int = 20) -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM notices ORDER BY id DESC LIMIT ?", conn, params=[limit])
    conn.close()
    return df


# 모듈 임포트 시 DB 초기화
init_db()
