import shutil
import sqlite3
import tempfile
import unittest

from data import database


class DatabaseSettingsSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp(prefix="archon_db_test_")
        cls._tmp_db_path = f"{cls._tmpdir}/portfolio.db"
        cls._orig_db_path = database.DB_PATH
        database.DB_PATH = cls._tmp_db_path
        database.init_db()

    @classmethod
    def tearDownClass(cls):
        database.DB_PATH = cls._orig_db_path
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_sensitive_value_round_trip_and_not_plain_in_db(self):
        username = "alice"
        setting_key = "openai_api_key"
        setting_value = "sk-test-value"

        database.save_user_setting(username, setting_key, setting_value)
        loaded = database.load_user_setting(username, setting_key)
        self.assertEqual(loaded, setting_value)

        conn = sqlite3.connect(database.DB_PATH)
        row = conn.execute(
            "SELECT setting_value FROM user_settings WHERE username=? AND setting_key=?",
            (username, setting_key),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], setting_value)

    def test_non_sensitive_value_round_trip(self):
        username = "bob"
        setting_key = "preferred_market"
        setting_value = "KR"

        database.save_user_setting(username, setting_key, setting_value)
        loaded = database.load_user_setting(username, setting_key)
        self.assertEqual(loaded, setting_value)

    def test_load_user_setting_default_when_missing(self):
        loaded = database.load_user_setting("nobody", "missing_key", default="fallback")
        self.assertEqual(loaded, "fallback")

    def test_save_user_setting_overwrite(self):
        username = "overwrite_user"
        setting_key = "preferred_market"
        database.save_user_setting(username, setting_key, "KR")
        database.save_user_setting(username, setting_key, "US")
        loaded = database.load_user_setting(username, setting_key)
        self.assertEqual(loaded, "US")

    def test_payment_receipt_idempotency(self):
        first = database.record_payment_receipt(
            provider="stripe",
            payment_id="cs_test_123",
            username="alice",
            plan_type="monthly",
            amount=99000,
            currency="krw",
        )
        second = database.record_payment_receipt(
            provider="stripe",
            payment_id="cs_test_123",
            username="alice",
            plan_type="monthly",
            amount=99000,
            currency="krw",
        )
        self.assertTrue(first)
        self.assertFalse(second)

    def test_apply_verified_payment_applies_plan_atomically(self):
        conn = sqlite3.connect(database.DB_PATH)
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
        conn.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, salt, role, plan) VALUES (?, ?, ?, ?, ?)",
            ("pay_user", "h", "s", "user", "free"),
        )
        conn.commit()
        conn.close()

        status_first = database.apply_verified_payment(
            provider="stripe",
            payment_id="cs_test_atomic",
            username="pay_user",
            plan_type="monthly",
            amount=99000,
            currency="krw",
        )
        status_second = database.apply_verified_payment(
            provider="stripe",
            payment_id="cs_test_atomic",
            username="pay_user",
            plan_type="monthly",
            amount=99000,
            currency="krw",
        )

        conn = sqlite3.connect(database.DB_PATH)
        user_row = conn.execute("SELECT plan FROM users WHERE username=?", ("pay_user",)).fetchone()
        conn.close()

        self.assertEqual(status_first, "applied")
        self.assertEqual(status_second, "duplicate")
        self.assertIsNotNone(user_row)
        self.assertEqual(user_row[0], "pro")

    def test_marketing_automation_job_and_due_cycle(self):
        database.upsert_marketing_automation_job(
            username="marketing_user",
            run_type="SNS 포스트",
            market="KOSPI",
            platform="트위터 (280자)",
            publish_channel="일반 웹훅",
            interval_minutes=60,
            webhook_url="",
            publish_notice=True,
            notify_on_failure=True,
            alert_email="ops@example.com",
            is_active=True,
        )

        job = database.get_marketing_automation_job("marketing_user")
        self.assertIsNotNone(job)
        if job is None:
            self.fail("marketing job should exist")
        self.assertTrue(job["is_active"])
        self.assertEqual(job["market"], "KOSPI")
        self.assertEqual(job["platform"], "트위터 (280자)")
        self.assertEqual(job["run_type"], "SNS 포스트")
        self.assertEqual(job["publish_channel"], "일반 웹훅")
        self.assertTrue(job["notify_on_failure"])
        self.assertEqual(job["alert_email"], "ops@example.com")

        conn = sqlite3.connect(database.DB_PATH)
        conn.execute(
            "UPDATE marketing_automation_jobs SET next_run_at='2000-01-01T00:00:00' WHERE username=?",
            ("marketing_user",),
        )
        conn.commit()
        conn.close()

        self.assertTrue(database.is_marketing_automation_due("marketing_user"))
        database.mark_marketing_automation_run("marketing_user")
        self.assertFalse(database.is_marketing_automation_due("marketing_user"))

    def test_marketing_automation_logs_round_trip(self):
        database.add_marketing_automation_log(
            username="marketing_user",
            run_type="SNS 포스트",
            status="success",
            message="ok",
            content_preview="preview",
        )
        logs = database.get_marketing_automation_logs("marketing_user", limit=5)
        self.assertFalse(logs.empty)
        self.assertIn("run_type", logs.columns)

    def test_session_token_limit_evicts_oldest(self):
        t1 = database.create_session_token(
            username="multi_user",
            user_id=101,
            role="user",
            plan="free",
            session_timeout=86400,
            max_sessions=2,
        )
        t2 = database.create_session_token(
            username="multi_user",
            user_id=101,
            role="user",
            plan="free",
            session_timeout=86400,
            max_sessions=2,
        )
        t3 = database.create_session_token(
            username="multi_user",
            user_id=101,
            role="user",
            plan="free",
            session_timeout=86400,
            max_sessions=2,
        )

        self.assertIsNone(database.validate_session_token(t1))
        self.assertIsNotNone(database.validate_session_token(t2))
        self.assertIsNotNone(database.validate_session_token(t3))


if __name__ == "__main__":
    unittest.main()
