import pandas as pd
import numpy as np
from typing import Optional
from pykrx import stock as krx
from datetime import datetime, timedelta
from analysis.technical import (
    calc_rsi, calc_macd, calc_sma, calc_bollinger,
    calc_stochastic, calc_adx, calc_williams_r, get_signal_summary,
    calc_ichimoku, calc_obv,
)


def _fetch_ohlcv(ticker: str, days: int = 120) -> pd.DataFrame:
    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    ohlcv = krx.get_market_ohlcv(start, today, ticker)
    if ohlcv.empty:
        return pd.DataFrame()
    ohlcv = ohlcv.rename(columns={
        "시가": "Open", "고가": "High", "저가": "Low",
        "종가": "Close", "거래량": "Volume"
    })
    return ohlcv


def _calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = calc_sma(df, [5, 20, 60])
    result = calc_rsi(result)
    result = calc_macd(result)
    result = calc_bollinger(result)
    result = calc_stochastic(result)
    result = calc_adx(result)
    result = calc_williams_r(result)
    try:
        result = calc_ichimoku(result)
    except Exception:
        pass
    try:
        result = calc_obv(result)
    except Exception:
        pass
    return result


def _momentum_score(df: pd.DataFrame) -> float:
    if len(df) < 20:
        return 0.0
    close = df["Close"]
    ret_5 = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
    ret_20 = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0
    ret_60 = (close.iloc[-1] / close.iloc[-61] - 1) * 100 if len(close) >= 61 else 0

    score = 0.0
    score += np.clip(ret_5 * 3, -15, 15)
    score += np.clip(ret_20 * 1.5, -20, 20)
    score += np.clip(ret_60 * 0.5, -15, 15)
    return round(float(score), 1)


def _volume_score(df: pd.DataFrame) -> float:
    if len(df) < 20 or "Volume" not in df.columns:
        return 0.0
    vol = df["Volume"]
    avg_vol = vol.rolling(20).mean().iloc[-1]
    if avg_vol == 0 or pd.isna(avg_vol):
        return 0.0
    ratio = vol.iloc[-1] / avg_vol
    if ratio >= 3.0:
        return 20.0
    elif ratio >= 2.0:
        return 15.0
    elif ratio >= 1.5:
        return 10.0
    elif ratio >= 1.0:
        return 5.0
    elif ratio >= 0.5:
        return 0.0
    else:
        return -10.0


def _volatility_penalty(df: pd.DataFrame) -> float:
    if len(df) < 20:
        return 0.0
    returns = df["Close"].pct_change().dropna()
    vol_20 = returns.tail(20).std() * np.sqrt(252) * 100
    if vol_20 > 80:
        return -20.0
    elif vol_20 > 60:
        return -10.0
    elif vol_20 > 40:
        return -5.0
    return 0.0


def _trend_consistency_score(df: pd.DataFrame) -> float:
    if len(df) < 20:
        return 0.0
    close = df["Close"]
    sma_5 = close.rolling(5).mean()
    sma_20 = close.rolling(20).mean()

    recent_5 = sma_5.tail(10)
    recent_20 = sma_20.tail(10)
    above_count = (recent_5 > recent_20).sum()

    if above_count >= 9:
        return 15.0
    elif above_count >= 7:
        return 10.0
    elif above_count <= 2:
        return -10.0
    elif above_count <= 4:
        return -5.0
    return 0.0


def recommend_stocks(
    market: str = "KOSPI",
    top_n: int = 50,
    result_count: int = 20,
) -> pd.DataFrame:
    today = datetime.now().strftime("%Y%m%d")
    tickers = krx.get_market_ticker_list(today, market=market)[:top_n]

    results = []
    for ticker in tickers:
        try:
            name = krx.get_market_ticker_name(ticker)
            df = _fetch_ohlcv(ticker, days=120)
            if df.empty or len(df) < 30:
                continue

            df_ind = _calc_all_indicators(df)
            tech = get_signal_summary(df_ind)
            tech_score = tech["score"]
            tech_signal = tech["signal"]

            mom_score = _momentum_score(df)
            vol_score = _volume_score(df)
            vol_penalty = _volatility_penalty(df)
            trend_score = _trend_consistency_score(df)

            # 가중 종합 점수 (-100 ~ 100)
            total = (
                tech_score * 0.35
                + mom_score * 0.25
                + vol_score * 0.15
                + trend_score * 0.15
                + vol_penalty * 0.10
            )
            total = max(-100, min(100, total))

            if total >= 30:
                recommendation = "강력 매수"
            elif total >= 15:
                recommendation = "매수"
            elif total >= 0:
                recommendation = "관망 (매수 우위)"
            elif total >= -15:
                recommendation = "관망 (매도 우위)"
            elif total >= -30:
                recommendation = "매도"
            else:
                recommendation = "강력 매도"

            close = df["Close"]
            current_price = int(close.iloc[-1])
            ret_1d = round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2) if len(close) >= 2 else 0
            ret_5d = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else 0
            ret_20d = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else 0

            rsi_val = df_ind["RSI"].iloc[-1] if "RSI" in df_ind.columns and not pd.isna(df_ind["RSI"].iloc[-1]) else None

            results.append({
                "종목코드": ticker,
                "종목명": name,
                "현재가": current_price,
                "1일(%)": ret_1d,
                "5일(%)": ret_5d,
                "20일(%)": ret_20d,
                "RSI": round(rsi_val, 1) if rsi_val else None,
                "기술점수": round(tech_score, 1),
                "모멘텀": round(mom_score, 1),
                "거래량": round(vol_score, 1),
                "추세일관성": round(trend_score, 1),
                "종합점수": round(total, 1),
                "추천": recommendation,
                "기술신호": tech_signal,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("종합점수", ascending=False).head(result_count)
    result_df = result_df.reset_index(drop=True)
    result_df.index = result_df.index + 1
    return result_df


def recommend_aggressive_stocks(
    market: str = "KOSPI",
    top_n: int = 100,
    result_count: int = 20,
) -> pd.DataFrame:
    today = datetime.now().strftime("%Y%m%d")
    tickers = krx.get_market_ticker_list(today, market=market)[:top_n]

    results = []
    for ticker in tickers:
        try:
            name = krx.get_market_ticker_name(ticker)
            df = _fetch_ohlcv(ticker, days=120)
            if df.empty or len(df) < 30:
                continue

            close = df["Close"]
            volume = df["Volume"]
            returns = close.pct_change().dropna()

            daily_vol = float(returns.tail(20).std() * np.sqrt(252) * 100)
            ret_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0
            ret_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
            ret_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else 0.0

            avg_vol_20 = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else 0
            vol_ratio = float(volume.iloc[-1] / avg_vol_20) if avg_vol_20 > 0 else 0

            df_ind = _calc_all_indicators(df)
            rsi_val = float(df_ind["RSI"].iloc[-1]) if "RSI" in df_ind.columns and not pd.isna(df_ind["RSI"].iloc[-1]) else 50.0

            vol_score = np.clip(daily_vol / 10, 0, 30)
            mom_score = np.clip(ret_20d * 2, -20, 40)
            vol_ratio_score = np.clip((vol_ratio - 1) * 10, 0, 30)
            rsi_score = 0.0
            if 40 < rsi_val < 70:
                rsi_score = 15.0
            elif rsi_val >= 70:
                rsi_score = -10.0
            elif rsi_val <= 30:
                rsi_score = 5.0

            total = vol_score * 0.25 + mom_score * 0.30 + vol_ratio_score * 0.25 + rsi_score * 0.20
            total = max(-50, min(100, total))

            if total < 10:
                continue

            max_gain_20 = float(returns.tail(20).max() * 100) if len(returns) >= 20 else 0
            max_loss_20 = float(returns.tail(20).min() * 100) if len(returns) >= 20 else 0

            if total >= 40:
                risk_label = "🔥🔥🔥 초고위험"
            elif total >= 25:
                risk_label = "🔥🔥 고위험"
            else:
                risk_label = "🔥 위험"

            results.append({
                "종목코드": ticker,
                "종목명": name,
                "현재가": int(close.iloc[-1]),
                "1일(%)": round(ret_1d, 2),
                "5일(%)": round(ret_5d, 2),
                "20일(%)": round(ret_20d, 2),
                "변동성(%)": round(daily_vol, 1),
                "거래량비율": round(vol_ratio, 1),
                "RSI": round(rsi_val, 1),
                "20일최대상승(%)": round(max_gain_20, 2),
                "20일최대하락(%)": round(max_loss_20, 2),
                "공격점수": round(total, 1),
                "위험등급": risk_label,
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("공격점수", ascending=False).head(result_count)
    result_df = result_df.reset_index(drop=True)
    result_df.index = result_df.index + 1
    return result_df
