import pandas as pd
import numpy as np
from typing import Optional
from pykrx import stock as krx
from datetime import datetime, timedelta
from itertools import product
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


def learn_optimal_weights(
    market: str = "KOSPI",
    lookback_days: int = 60,
    top_n: int = 50,
) -> dict:
    default_weights = {
        "tech_w": 0.35,
        "mom_w": 0.25,
        "vol_w": 0.15,
        "trend_w": 0.15,
        "vol_penalty_w": 0.10,
    }

    tech_weights = [0.2, 0.3, 0.4]
    mom_weights = [0.15, 0.25, 0.35]
    vol_weights = [0.1, 0.15, 0.2]
    trend_weights = [0.1, 0.15, 0.2]

    now = datetime.now()
    start_date = now - timedelta(days=max(lookback_days + 140, 220))
    eval_date = now - timedelta(days=lookback_days)
    end_str = now.strftime("%Y%m%d")
    start_str = start_date.strftime("%Y%m%d")

    tickers = []
    for offset in range(10):
        probe = (eval_date - timedelta(days=offset)).strftime("%Y%m%d")
        tickers = krx.get_market_ticker_list(probe, market=market)
        if tickers:
            break

    tickers = tickers[:top_n]
    if not tickers:
        return {
            "error": "학습 대상 종목이 없습니다.",
            "optimal_weights": default_weights,
            "default_weights": default_weights,
            "all_results": [],
        }

    samples = []
    for ticker in tickers:
        try:
            ohlcv = krx.get_market_ohlcv(start_str, end_str, ticker)
            if ohlcv.empty:
                continue

            df = ohlcv.rename(columns={
                "시가": "Open", "고가": "High", "저가": "Low",
                "종가": "Close", "거래량": "Volume"
            })
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            if len(df) < 90:
                continue

            past_df = df[df.index <= eval_date]
            future_df = df[df.index > eval_date]
            if len(past_df) < 60 or future_df.empty:
                continue

            ind_df = _calc_all_indicators(past_df)
            tech_info = get_signal_summary(ind_df)

            close_past = float(past_df["Close"].iloc[-1])
            close_now = float(future_df["Close"].iloc[-1])
            future_return = (close_now / close_past - 1) * 100

            samples.append({
                "ticker": ticker,
                "tech_score": float(tech_info.get("score", 0)),
                "mom_score": float(_momentum_score(past_df)),
                "vol_score": float(_volume_score(past_df)),
                "trend_score": float(_trend_consistency_score(past_df)),
                "vol_penalty": float(_volatility_penalty(past_df)),
                "future_return": float(future_return),
            })
        except Exception:
            continue

    if len(samples) < 10:
        return {
            "error": "학습 가능한 종목 수가 부족합니다.",
            "optimal_weights": default_weights,
            "default_weights": default_weights,
            "stock_count": len(samples),
            "all_results": [],
        }

    sample_df = pd.DataFrame(samples)
    top_bucket = max(5, min(20, int(len(sample_df) * 0.2)))

    def evaluate(weights: dict) -> dict:
        score = (
            sample_df["tech_score"] * weights["tech_w"]
            + sample_df["mom_score"] * weights["mom_w"]
            + sample_df["vol_score"] * weights["vol_w"]
            + sample_df["trend_score"] * weights["trend_w"]
            + sample_df["vol_penalty"] * weights["vol_penalty_w"]
        )

        ranked = sample_df.assign(pred_score=score).sort_values("pred_score", ascending=False)
        top_return = float(ranked.head(top_bucket)["future_return"].mean())
        corr = float(ranked["pred_score"].corr(ranked["future_return"]))
        if pd.isna(corr):
            corr = 0.0

        return {
            "weights": weights,
            "top_return": round(top_return, 4),
            "corr": round(corr, 4),
        }

    combo_results = []
    for tech_w, mom_w, vol_w, trend_w in product(tech_weights, mom_weights, vol_weights, trend_weights):
        w = {
            "tech_w": tech_w,
            "mom_w": mom_w,
            "vol_w": vol_w,
            "trend_w": trend_w,
            "vol_penalty_w": default_weights["vol_penalty_w"],
        }
        combo_results.append(evaluate(w))

    combo_results = sorted(combo_results, key=lambda x: (x["top_return"], x["corr"]), reverse=True)
    best = combo_results[0]
    default_eval = evaluate(default_weights)

    improvement = best["top_return"] - default_eval["top_return"]
    return {
        "market": market,
        "lookback_days": lookback_days,
        "stock_count": int(len(sample_df)),
        "top_bucket": int(top_bucket),
        "optimal_weights": best["weights"],
        "default_weights": default_weights,
        "comparison": {
            "default_top_return": float(default_eval["top_return"]),
            "optimized_top_return": float(best["top_return"]),
            "improvement": float(round(improvement, 4)),
            "default_corr": float(default_eval["corr"]),
            "optimized_corr": float(best["corr"]),
        },
        "all_results": combo_results,
    }
