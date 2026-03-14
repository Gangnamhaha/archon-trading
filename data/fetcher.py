"""
주가 데이터 수집 모듈
- 미국 주식: yfinance
- 한국 주식: pykrx
"""
import pandas as pd
from functools import lru_cache
import yfinance as yf
from pykrx import stock as krx
from datetime import datetime, timedelta


def fetch_us_stock(ticker: str, period: str = "1y") -> pd.DataFrame:
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            if data.empty:
                if attempt < max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return pd.DataFrame()
            cols = ["Open", "High", "Low", "Close", "Volume"]
            available = [c for c in cols if c in data.columns]
            if len(available) < 5:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                available = [c for c in cols if c in data.columns]
            data = data[available].copy()
            data.index.name = "Date"
            if data.index.tz is not None:
                data.index = data.index.tz_localize(None)
            return data
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"[ERROR] US stock fetch failed ({ticker}): {e}")
            return pd.DataFrame()


def fetch_kr_stock(ticker: str, start: str = None, end: str = None, period: str = "1y") -> pd.DataFrame:
    """한국 주가 데이터 조회 (pykrx)"""
    try:
        if end is None:
            end = datetime.now().strftime("%Y%m%d")
        if start is None:
            period_map = {
                "1mo": 30, "3mo": 90, "6mo": 180,
                "1y": 365, "2y": 730, "5y": 1825, "max": 3650,
            }
            days = period_map.get(period, 365)
            start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        data = krx.get_market_ohlcv(start, end, ticker)
        if data.empty:
            return pd.DataFrame()

        data = data.rename(columns={
            "시가": "Open", "고가": "High", "저가": "Low",
            "종가": "Close", "거래량": "Volume"
        })
        data = data[["Open", "High", "Low", "Close", "Volume"]].copy()
        data.index.name = "Date"
        return data
    except Exception as e:
        print(f"[ERROR] 한국 주가 조회 실패 ({ticker}): {e}")
        return pd.DataFrame()


@lru_cache(maxsize=128)
def fetch_stock(ticker: str, market: str = "US", period: str = "1y") -> pd.DataFrame:
    """통합 주가 조회 함수"""
    if market.upper() == "US":
        return fetch_us_stock(ticker, period)
    elif market.upper() == "KR":
        return fetch_kr_stock(ticker, period=period)
    else:
        raise ValueError(f"지원하지 않는 시장: {market}")


def get_kr_stock_list() -> pd.DataFrame:
    """한국 KRX 종목 리스트 조회"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        tickers = krx.get_market_ticker_list(today, market="ALL")
        stocks = []
        for t in tickers:
            name = krx.get_market_ticker_name(t)
            stocks.append({"ticker": t, "name": name})
        return pd.DataFrame(stocks)
    except Exception as e:
        print(f"[ERROR] 한국 종목 리스트 조회 실패: {e}")
        return pd.DataFrame(columns=["ticker", "name"])


def get_us_popular_stocks() -> pd.DataFrame:
    """주요 미국 종목 리스트"""
    stocks = [
        {"ticker": "AAPL", "name": "Apple Inc."},
        {"ticker": "MSFT", "name": "Microsoft Corp."},
        {"ticker": "GOOGL", "name": "Alphabet Inc."},
        {"ticker": "AMZN", "name": "Amazon.com Inc."},
        {"ticker": "NVDA", "name": "NVIDIA Corp."},
        {"ticker": "META", "name": "Meta Platforms Inc."},
        {"ticker": "TSLA", "name": "Tesla Inc."},
        {"ticker": "BRK-B", "name": "Berkshire Hathaway"},
        {"ticker": "JPM", "name": "JPMorgan Chase"},
        {"ticker": "V", "name": "Visa Inc."},
        {"ticker": "JNJ", "name": "Johnson & Johnson"},
        {"ticker": "WMT", "name": "Walmart Inc."},
        {"ticker": "MA", "name": "Mastercard Inc."},
        {"ticker": "PG", "name": "Procter & Gamble"},
        {"ticker": "DIS", "name": "Walt Disney Co."},
        {"ticker": "NFLX", "name": "Netflix Inc."},
        {"ticker": "AMD", "name": "AMD Inc."},
        {"ticker": "INTC", "name": "Intel Corp."},
        {"ticker": "CRM", "name": "Salesforce Inc."},
        {"ticker": "PYPL", "name": "PayPal Holdings"},
        {"ticker": "SPY", "name": "S&P 500 ETF"},
        {"ticker": "QQQ", "name": "Nasdaq 100 ETF"},
    ]
    return pd.DataFrame(stocks)
