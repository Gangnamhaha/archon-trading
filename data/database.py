"""
SQLite 데이터베이스 모듈
- 포트폴리오 데이터 관리
- 거래 이력 관리
"""
import sqlite3
import os
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")


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

    conn.commit()
    conn.close()


# === 포트폴리오 CRUD ===

def add_stock(ticker: str, market: str, name: str, buy_price: float, quantity: int, buy_date: str = None):
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


def update_stock(stock_id: int, buy_price: float = None, quantity: int = None):
    """포트폴리오 종목 수정"""
    conn = get_connection()
    if buy_price is not None:
        conn.execute("UPDATE portfolio SET buy_price = ? WHERE id = ?", (buy_price, stock_id))
    if quantity is not None:
        conn.execute("UPDATE portfolio SET quantity = ? WHERE id = ?", (quantity, stock_id))
    conn.commit()
    conn.close()


# === 거래 이력 ===

def add_trade(ticker: str, market: str, action: str, price: float, quantity: int, strategy: str = None):
    """거래 이력 추가"""
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO trade_history (ticker, market, action, price, quantity, strategy) VALUES (?, ?, ?, ?, ?, ?)",
        (ticker, market, action, price, quantity, strategy)
    )
    conn.commit()
    conn.close()


def get_trades(ticker: str = None, limit: int = 100) -> pd.DataFrame:
    """거래 이력 조회"""
    init_db()
    conn = get_connection()
    if ticker:
        df = pd.read_sql_query(
            "SELECT * FROM trade_history WHERE ticker = ? ORDER BY timestamp DESC LIMIT ?",
            conn, params=(ticker, limit)
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM trade_history ORDER BY timestamp DESC LIMIT ?",
            conn, params=(limit,)
        )
    conn.close()
    return df


# 모듈 임포트 시 DB 초기화
init_db()
