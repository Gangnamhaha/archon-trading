"""
주가 데이터 수집 모듈
- 미국 주식: yfinance
- 한국 주식: pykrx
"""
import pandas as pd
from functools import lru_cache
from typing import Optional, cast
import yfinance as yf
from pykrx import stock as krx
from datetime import datetime, timedelta


def _normalize_us_period_for_interval(period: str, interval: str) -> str:
    """yfinance intraday 제한에 맞춰 period 보정"""
    intraday_limits = {
        "1m": "7d",
        "2m": "60d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "60m": "730d",
        "90m": "60d",
        "1h": "730d",
    }
    if interval not in intraday_limits:
        return period

    order = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]
    max_period = intraday_limits[interval]
    if period not in order or max_period not in order:
        return max_period
    return period if order.index(period) <= order.index(max_period) else max_period


def fetch_us_stock(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            clean_ticker = str(ticker or "").strip().upper()
            if not clean_ticker:
                return pd.DataFrame()
            effective_period = _normalize_us_period_for_interval(str(period or "1y"), str(interval or "1d"))
            stock = yf.Ticker(clean_ticker)
            data = stock.history(period=effective_period, interval=str(interval or "1d"))
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
            index_tz = getattr(data.index, "tz", None)
            tz_localize = getattr(data.index, "tz_localize", None)
            if index_tz is not None and callable(tz_localize):
                data.index = pd.Index(tz_localize(None))
            return cast(pd.DataFrame, data)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"[ERROR] US stock fetch failed ({ticker}): {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def fetch_kr_stock(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    period: str = "1y",
) -> pd.DataFrame:
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
        return cast(pd.DataFrame, data)
    except Exception as e:
        print(f"[ERROR] 한국 주가 조회 실패 ({ticker}): {e}")
        return pd.DataFrame()


@lru_cache(maxsize=128)
def fetch_stock(ticker: str, market: str = "US", period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """통합 주가 조회 함수"""
    if market.upper() == "US":
        return fetch_us_stock(ticker, period, interval)
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
        return pd.DataFrame({"ticker": pd.Series(dtype=str), "name": pd.Series(dtype=str)})


# ─── FX (외환) ────────────────────────────────────────────────────────────────

FX_PAIRS: dict[str, str] = {
    "USD/KRW": "USDKRW=X",
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "USD/CNY": "USDCNY=X",
    "EUR/KRW": "EURKRW=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CHF": "USDCHF=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
}


def fetch_fx_pair(pair: str, period: str = "1y") -> pd.DataFrame:
    """외환 쌍 OHLCV 데이터 조회 (yfinance)"""
    ticker_sym = FX_PAIRS.get(pair, pair)
    try:
        import time
        for attempt in range(3):
            try:
                t = yf.Ticker(ticker_sym)
                data = t.history(period=period)
                if data.empty:
                    if attempt < 2:
                        time.sleep(1.5)
                        continue
                    return pd.DataFrame()
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
                data = data[cols].copy()
                index_tz = getattr(data.index, "tz", None)
                tz_localize = getattr(data.index, "tz_localize", None)
                if index_tz is not None and callable(tz_localize):
                    data.index = pd.Index(tz_localize(None))
                data.index.name = "Date"
                return cast(pd.DataFrame, data)
            except Exception:
                if attempt < 2:
                    time.sleep(1.5)
                    continue
    except Exception as e:
        print(f"[ERROR] FX fetch failed ({pair}): {e}")
    return pd.DataFrame()


def get_fx_spot_rate(pair: str) -> float:
    """외환 현재 환율 조회"""
    df = fetch_fx_pair(pair, period="5d")
    if df.empty or "Close" not in df.columns:
        return 0.0
    return float(df["Close"].iloc[-1])


# ─── Crypto (코인) ───────────────────────────────────────────────────────────

CRYPTO_PAIRS: dict[str, str] = {
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "BNB/USD": "BNB-USD",
    "XRP/USD": "XRP-USD",
    "SOL/USD": "SOL-USD",
    "ADA/USD": "ADA-USD",
    "DOGE/USD": "DOGE-USD",
    "AVAX/USD": "AVAX-USD",
    "DOT/USD": "DOT-USD",
    "MATIC/USD": "MATIC-USD",
    "LINK/USD": "LINK-USD",
    "LTC/USD": "LTC-USD",
    "BCH/USD": "BCH-USD",
    "ATOM/USD": "ATOM-USD",
    "UNI/USD": "UNI-USD",
}


def fetch_crypto(symbol: str, period: str = "1y") -> pd.DataFrame:
    """암호화폐 OHLCV 데이터 조회 (yfinance)"""
    ticker_sym = CRYPTO_PAIRS.get(symbol, symbol)
    return fetch_us_stock(ticker_sym, period=period)


def get_crypto_price(symbol: str) -> float:
    """코인 현재 가격 조회 (USD)"""
    df = fetch_crypto(symbol, period="5d")
    if df.empty or "Close" not in df.columns:
        return 0.0
    return float(df["Close"].iloc[-1])




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
