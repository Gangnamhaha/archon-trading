import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from importlib import import_module, reload
from unittest.mock import patch


class _FakeQueryParams(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def clear(self):
        self.update({k: None for k in list(self.keys())})
        for k in list(self.keys()):
            del self[k]


class _FakeStreamlit:
    def __init__(self, state=None):
        self.session_state = state or {}
        self.query_params = _FakeQueryParams()
        self.warning_called = False
        self.rerun_called = False
        self.markdown_called = False

    def warning(self, _message):
        self.warning_called = True

    def rerun(self):
        self.rerun_called = True

    def stop(self):
        raise RuntimeError("streamlit stop")

    def markdown(self, *args, **kwargs):
        self.markdown_called = True


class AuthSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sqlite3

        cls._tmpdir = tempfile.mkdtemp(prefix="archon_auth_test_")
        cls._tmp_db_path = f"{cls._tmpdir}/portfolio.db"
        original_connect = sqlite3.connect
        cls._orig_sqlite_connect = original_connect

        def _redirect_connect(_db_path, *args, **kwargs):
            return original_connect(cls._tmp_db_path, *args, **kwargs)

        sqlite3.connect = _redirect_connect
        try:
            auth_mod = import_module("config.auth")
            cls.auth = reload(auth_mod)
        finally:
            sqlite3.connect = original_connect

        cls._orig_db_path = getattr(cls.auth, "DB_PATH")
        setattr(cls.auth, "DB_PATH", cls._tmp_db_path)
        cls.auth._init_users_table()

    @classmethod
    def tearDownClass(cls):
        setattr(cls.auth, "DB_PATH", cls._orig_db_path)
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_admin_default_password_works(self):
        user = self.auth.verify_user("admin", "7777")
        self.assertIsNotNone(user)
        if user is None:
            self.fail("admin user should exist")
        self.assertEqual(user["username"], "admin")
        self.assertEqual(user["role"], "admin")
        self.assertEqual(user["plan"], "pro")

    def test_create_and_verify_regular_user_and_negative_cases(self):
        created = self.auth.create_user("smoke_user", "secret123", role="user", plan="free")
        self.assertTrue(created)
        verified = self.auth.verify_user("smoke_user", "secret123")
        self.assertIsNotNone(verified)
        if verified is None:
            self.fail("created user should be verifiable")
        self.assertEqual(verified["role"], "user")
        self.assertEqual(verified["plan"], "free")
        self.assertIsNone(self.auth.verify_user("smoke_user", "wrong-password"))
        self.assertIsNone(self.auth.verify_user("missing-user", "secret123"))
        self.assertFalse(self.auth.create_user("smoke_user", "secret123"))

    def test_check_session_expiry_clears_expired_session(self):
        fake_st = _FakeStreamlit(
            {
                "authenticated": True,
                "user": {"id": 1, "username": "admin", "role": "admin", "plan": "pro"},
                "_login_time": datetime.now() - timedelta(seconds=5),
                "_last_activity_time": datetime.now() - timedelta(seconds=5),
                "_session_timeout": 1,
            }
        )
        with patch.object(self.auth, "st", fake_st):
            self.auth._check_session_expiry()

        self.assertEqual(fake_st.session_state, {})
        self.assertTrue(fake_st.warning_called)
        self.assertTrue(fake_st.rerun_called)

    def test_require_auth_stops_when_unauthenticated(self):
        fake_st = _FakeStreamlit({"authenticated": False})

        def _fake_login_form():
            fake_st.session_state["login_form_shown"] = True

        with patch.object(self.auth, "st", fake_st), patch.object(self.auth, "_show_login_form", _fake_login_form):
            with self.assertRaises(RuntimeError):
                self.auth.require_auth()

        self.assertTrue(fake_st.session_state.get("login_form_shown", False))


if __name__ == "__main__":
    unittest.main()
