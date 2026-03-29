"""
경량 SQLite 마이그레이션 시스템

- data/migrations/ 디렉토리에 001_description.py, 002_description.py ... 형태로 추가
- 각 파일은 upgrade(conn) 함수를 정의
- schema_migrations 테이블로 적용 이력 관리
"""

import importlib.util
import os
import sqlite3
from datetime import datetime

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def _init_migration_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """
    )
    conn.commit()


def _get_applied(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def _discover_migrations() -> list[tuple[str, str]]:
    """(version, filepath) 리스트를 버전순으로 반환."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".py") and not f.startswith("_"))
    result = []
    for f in files:
        version = f.split("_", 1)[0]
        result.append((version, os.path.join(MIGRATIONS_DIR, f)))
    return result


def _load_module(filepath: str):
    spec = importlib.util.spec_from_file_location("migration", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_migrations(db_path: str) -> list[str]:
    """미적용 마이그레이션을 순서대로 실행. 적용된 버전 목록을 반환."""
    conn = sqlite3.connect(db_path)
    _init_migration_table(conn)
    applied = _get_applied(conn)
    migrations = _discover_migrations()

    newly_applied = []
    for version, filepath in migrations:
        if version in applied:
            continue
        mod = _load_module(filepath)
        mod.upgrade(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now().isoformat()),
        )
        conn.commit()
        newly_applied.append(version)

    conn.close()
    return newly_applied


def get_status(db_path: str) -> dict:
    """마이그레이션 상태를 반환."""
    conn = sqlite3.connect(db_path)
    _init_migration_table(conn)
    applied = _get_applied(conn)
    conn.close()
    migrations = _discover_migrations()
    pending = [v for v, _ in migrations if v not in applied]
    return {"applied": sorted(applied), "pending": pending, "total": len(migrations)}
