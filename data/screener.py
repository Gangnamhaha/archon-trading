"""
종목 스크리너 모듈
- 기술적 지표 기반 종목 필터링
- 다중 조건 스크리닝
"""
import pandas as pd
from pykrx import stock as krx
from datetime import datetime, timedelta
from typing import cast
from analysis.technical import calc_rsi, calc_macd, calc_sma, calc_bollinger


REQUIRED_KRX_OHLCV_COLUMNS = {"시가", "고가", "저가", "종가", "거래량"}


def get_krx_market_data(market: str = "KOSPI", top_n: int = 100) -> pd.DataFrame:
    """KRX 시가총액 상위 종목 시장 데이터"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        tickers = krx.get_market_ticker_list(today, market=market)[:top_n]

        results = []
        for ticker in tickers:
            try:
                name = krx.get_market_ticker_name(ticker)

                # 최근 60일 데이터
                start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
                ohlcv = krx.get_market_ohlcv(start, today, ticker)
                if ohlcv.empty or len(ohlcv) < 20:
                    continue
                if not REQUIRED_KRX_OHLCV_COLUMNS.issubset(set(ohlcv.columns.astype(str).tolist())):
                    continue

                ohlcv = ohlcv.rename(columns={
                    "시가": "Open", "고가": "High", "저가": "Low",
                    "종가": "Close", "거래량": "Volume"
                })

                close = cast(pd.Series, ohlcv["Close"])
                latest = close.iloc[-1]

                # 기본 지표 계산
                sma_5 = cast(pd.Series, close.rolling(5).mean()).iloc[-1]
                sma_20 = cast(pd.Series, close.rolling(20).mean()).iloc[-1]
                sma_60 = cast(pd.Series, close.rolling(60).mean()).iloc[-1] if len(close) >= 60 else None

                # RSI
                rsi_df = calc_rsi(ohlcv)
                rsi_val = rsi_df["RSI"].iloc[-1]

                # MACD
                macd_df = calc_macd(ohlcv)
                macd_val = macd_df["MACD"].iloc[-1]
                macd_signal = macd_df["MACD_Signal"].iloc[-1]

                # 수익률
                return_1d = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0
                return_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
                return_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0

                # 거래량 평균 대비
                vol_ratio = ohlcv["Volume"].iloc[-1] / ohlcv["Volume"].mean() if ohlcv["Volume"].mean() > 0 else 0

                results.append({
                    "종목코드": ticker,
                    "종목명": name,
                    "현재가": int(latest),
                    "1일수익률(%)": round(return_1d, 2),
                    "5일수익률(%)": round(return_5d, 2),
                    "20일수익률(%)": round(return_20d, 2),
                    "RSI": round(rsi_val, 1) if not pd.isna(rsi_val) else None,
                    "MACD": round(macd_val, 2) if not pd.isna(macd_val) else None,
                    "MACD_Signal": round(macd_signal, 2) if not pd.isna(macd_signal) else None,
                    "SMA_5": round(sma_5, 0) if not pd.isna(sma_5) else None,
                    "SMA_20": round(sma_20, 0) if not pd.isna(sma_20) else None,
                    "SMA_60": round(sma_60, 0) if sma_60 and not pd.isna(sma_60) else None,
                    "거래량비율": round(vol_ratio, 2),
                })
            except Exception:
                continue

        return pd.DataFrame(results)
    except Exception as e:
        print(f"[ERROR] 스크리너 데이터 수집 실패: {e}")
        return pd.DataFrame()


def screen_stocks(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    조건 기반 종목 필터링
    filters 예시:
    {
        "RSI_min": 20, "RSI_max": 80,
        "MACD_cross": "golden",  # golden, dead
        "SMA_trend": "up",  # up, down
        "return_1d_min": -5, "return_1d_max": 5,
        "vol_ratio_min": 1.5,
    }
    """
    result = df.copy()

    # RSI 필터
    if "RSI_min" in filters:
        result = result[result["RSI"] >= filters["RSI_min"]]
    if "RSI_max" in filters:
        result = result[result["RSI"] <= filters["RSI_max"]]

    # MACD 크로스 필터
    if "MACD_cross" in filters:
        if filters["MACD_cross"] == "golden":
            result = result[result["MACD"] > result["MACD_Signal"]]
        elif filters["MACD_cross"] == "dead":
            result = result[result["MACD"] < result["MACD_Signal"]]

    # SMA 추세 필터
    if "SMA_trend" in filters:
        if filters["SMA_trend"] == "up":
            result = result[result["SMA_5"] > result["SMA_20"]]
        elif filters["SMA_trend"] == "down":
            result = result[result["SMA_5"] < result["SMA_20"]]

    # 수익률 필터
    if "return_1d_min" in filters:
        result = result[result["1일수익률(%)"] >= filters["return_1d_min"]]
    if "return_1d_max" in filters:
        result = result[result["1일수익률(%)"] <= filters["return_1d_max"]]
    if "return_20d_min" in filters:
        result = result[result["20일수익률(%)"] >= filters["return_20d_min"]]
    if "return_20d_max" in filters:
        result = result[result["20일수익률(%)"] <= filters["return_20d_max"]]

    # 거래량 비율 필터
    if "vol_ratio_min" in filters:
        result = result[result["거래량비율"] >= filters["vol_ratio_min"]]

    return pd.DataFrame(result).reset_index(drop=True)


# 프리셋 스크리너
PRESETS = {
    "과매도 반등 후보": {"RSI_max": 30},
    "골든크로스 종목": {"MACD_cross": "golden", "SMA_trend": "up"},
    "급등 종목 (거래량 폭증)": {"vol_ratio_min": 3.0, "return_1d_min": 2},
    "안정적 상승 종목": {"RSI_min": 40, "RSI_max": 60, "SMA_trend": "up", "return_20d_min": 5},
    "과매수 주의 종목": {"RSI_min": 70},
}
