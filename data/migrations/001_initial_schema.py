"""
초기 스키마 마이그레이션 — 기존 테이블이 없는 경우에만 생성.
이미 운영 중인 DB는 이 마이그레이션이 no-op으로 적용됩니다.
"""


def upgrade(conn):
    stmts = [
        # auth/core.py
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS user_plan_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            expires_at TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS login_attempts (
            username TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS admin_totp (
            user_id INTEGER PRIMARY KEY,
            secret TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        # data/database.py
        """CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            quantity REAL NOT NULL,
            buy_price REAL NOT NULL,
            buy_date TEXT,
            market TEXT DEFAULT 'KR',
            currency TEXT DEFAULT 'KRW',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            strategy TEXT DEFAULT '',
            traded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT DEFAULT 'KR',
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, ticker)
        )""",
        """CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            setting_key TEXT NOT NULL,
            setting_value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, setting_key)
        )""",
        """CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS user_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS referral_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            used_by TEXT DEFAULT '',
            reward_applied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS newsletter_subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            subscribed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT DEFAULT 'admin',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS autopilot_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            slot INTEGER NOT NULL DEFAULT 1,
            market TEXT NOT NULL DEFAULT 'KR',
            mode TEXT NOT NULL DEFAULT 'conservative',
            status TEXT NOT NULL DEFAULT 'running',
            broker TEXT DEFAULT '',
            interval_sec INTEGER DEFAULT 60,
            stop_loss REAL DEFAULT 0.0,
            take_profit REAL DEFAULT 0.0,
            daily_loss_limit REAL DEFAULT 0.0,
            max_stocks INTEGER DEFAULT 5,
            budget REAL DEFAULT 0.0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, slot)
        )""",
        """CREATE TABLE IF NOT EXISTS autopilot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            ticker TEXT,
            action TEXT,
            quantity REAL,
            price REAL,
            reason TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS session_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            device_info TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            ip_address TEXT DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS customer_inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            admin_reply TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS marketing_automation_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            name TEXT NOT NULL,
            job_type TEXT NOT NULL DEFAULT 'webhook',
            schedule TEXT NOT NULL DEFAULT 'daily',
            target_url TEXT DEFAULT '',
            payload_template TEXT DEFAULT '',
            headers TEXT DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'active',
            last_run_at TEXT,
            next_run_at TEXT,
            run_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            notify_on_fail INTEGER DEFAULT 1,
            notify_email TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS marketing_automation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            response_code INTEGER,
            response_body TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            executed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS payment_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            provider TEXT NOT NULL,
            receipt_id TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'KRW',
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS app_error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT DEFAULT '',
            page TEXT DEFAULT '',
            error_type TEXT DEFAULT '',
            message TEXT NOT NULL,
            traceback TEXT DEFAULT '',
            severity TEXT DEFAULT 'error',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
    ]
    for stmt in stmts:
        conn.execute(stmt)
    conn.commit()
