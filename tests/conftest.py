import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _patch_streamlit(monkeypatch):
    try:
        import streamlit as st
        if not hasattr(st, "session_state"):
            monkeypatch.setattr(st, "session_state", {})
    except ImportError:
        pass


@pytest.fixture()
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["ARCHON_DB_PATH"] = db_path
    yield db_path
    os.environ.pop("ARCHON_DB_PATH", None)
