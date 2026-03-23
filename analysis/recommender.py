# pyright: basic
import pandas as pd
import numpy as np
from typing import Optional, Any, cast
from pykrx import stock as krx
import yfinance as yf
from datetime import datetime, timedelta
from functools import lru_cache
from itertools import product
from analysis.technical import (
    calc_rsi, calc_macd, calc_sma, calc_bollinger,
    calc_stochastic, calc_adx, calc_williams_r, get_signal_summary,
    calc_ichimoku, calc_obv,
)


def _get_recent_market_tickers(market: str, max_days_back: int = 10) -> list[str]:
    market_key = (market or "KOSPI").upper()
    today = datetime.now()
    for offset in range(max_days_back + 1):
        probe = (today - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            tickers = [str(t) for t in krx.get_market_ticker_list(probe, market=market_key)]
        except Exception:
            tickers = []
        if tickers:
            return tickers
    fallback = {
        "KOSPI": ["005930", "000660", "035420", "051910", "005380", "068270", "105560", "012330"],
        "KOSDAQ": ["247540", "086520", "196170", "263750", "293490", "067310", "278280", "041510"],
    }
    return list(fallback.get(market_key, []))


def _empty_dataframe_with_columns(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame({col: pd.Series(dtype=object) for col in columns})


def _fetch_ohlcv_via_yfinance(ticker: str, days: int = 120) -> pd.DataFrame:
    period_days = max(int(days), 120)
    period = f"{period_days}d"
    suffixes = [".KS", ".KQ"]
    for suffix in suffixes:
        try:
            hist = yf.Ticker(f"{ticker}{suffix}").history(period=period, interval="1d")
            if hist.empty:
                continue
            required = ["Open", "High", "Low", "Close", "Volume"]
            if not set(required).issubset(set(hist.columns.astype(str).tolist())):
                continue
            out = hist[required].copy()
            out.index.name = "Date"
            return cast(pd.DataFrame, out)
        except Exception:
            continue
    return pd.DataFrame()


def _series_from_column(df: pd.DataFrame, column: str) -> pd.Series:
    raw = df[column]
    if isinstance(raw, pd.DataFrame):
        base_series = raw.iloc[:, 0]
    else:
        base_series = pd.Series(raw)
    numeric = pd.to_numeric(base_series, errors="coerce")
    return cast(pd.Series, pd.Series(numeric, dtype=float))


@lru_cache(maxsize=256)
def _fetch_ohlcv(ticker: str, days: int = 120) -> pd.DataFrame:
    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    try:
        ohlcv = krx.get_market_ohlcv(start, today, ticker)
    except Exception:
        ohlcv = pd.DataFrame()
    if ohlcv.empty:
        return _fetch_ohlcv_via_yfinance(ticker, days=days)
    required = {"시가", "고가", "저가", "종가", "거래량"}
    if not required.issubset(set(ohlcv.columns.astype(str).tolist())):
        return _fetch_ohlcv_via_yfinance(ticker, days=days)
    ohlcv = ohlcv.rename(columns={
        "시가": "Open", "고가": "High", "저가": "Low",
        "종가": "Close", "거래량": "Volume"
    })
    required_renamed = ["Open", "High", "Low", "Close", "Volume"]
    if not set(required_renamed).issubset(set(ohlcv.columns.astype(str).tolist())):
        return _fetch_ohlcv_via_yfinance(ticker, days=days)
    return cast(pd.DataFrame, ohlcv[required_renamed].copy())


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
    close = _series_from_column(df, "Close").dropna()
    if len(close) < 6:
        return 0.0

    ret_5 = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0.0
    ret_20 = (float(close.iloc[-1]) / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0.0
    ret_60 = (float(close.iloc[-1]) / float(close.iloc[-61]) - 1) * 100 if len(close) >= 61 else 0.0

    score = 0.0
    score += np.clip(ret_5 * 3, -15, 15)
    score += np.clip(ret_20 * 1.5, -20, 20)
    score += np.clip(ret_60 * 0.5, -15, 15)
    return round(float(score), 1)


def _volume_score(df: pd.DataFrame) -> float:
    if len(df) < 20 or "Volume" not in df.columns:
        return 0.0
    vol = _series_from_column(df, "Volume").dropna()
    if len(vol) < 20:
        return 0.0

    vol_ma_raw = vol.rolling(20).mean()
    vol_ma = vol_ma_raw if isinstance(vol_ma_raw, pd.Series) else pd.Series(vol_ma_raw, dtype=float)
    avg_vol = float(vol_ma.iloc[-1]) if not vol_ma.empty else 0.0
    if avg_vol == 0 or pd.isna(avg_vol):
        return 0.0
    ratio = float(vol.iloc[-1]) / avg_vol
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
    returns = _series_from_column(df, "Close").pct_change().dropna()
    if len(returns) < 20:
        return 0.0

    vol_20 = float(returns.tail(20).std() * np.sqrt(252) * 100)
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
    close = _series_from_column(df, "Close").dropna()
    if len(close) < 20:
        return 0.0

    sma_5_raw = close.rolling(5).mean()
    sma_20_raw = close.rolling(20).mean()
    recent_5 = np.asarray(sma_5_raw, dtype=float)[-10:]
    recent_20 = np.asarray(sma_20_raw, dtype=float)[-10:]
    above_count = int((recent_5 > recent_20).sum())

    if above_count >= 9:
        return 15.0
    elif above_count >= 7:
        return 10.0
    elif above_count <= 2:
        return -10.0
    elif above_count <= 4:
        return -5.0
    return 0.0


@lru_cache(maxsize=1024)
def _get_ticker_name(ticker: str) -> str:
    try:
        return krx.get_market_ticker_name(ticker)
    except Exception:
        return ticker


@lru_cache(maxsize=2048)
def _get_returns_series(ticker: str, days: int = 120) -> pd.Series:
    df = _fetch_ohlcv(ticker, days=days)
    if df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)
    close = _series_from_column(df, "Close")
    returns = close.pct_change().dropna()
    if returns.empty:
        return pd.Series(dtype=float)
    return cast(pd.Series, pd.Series(returns, dtype=float))


@lru_cache(maxsize=1024)
def _candidate_factor_snapshot(ticker: str, days: int = 120) -> Optional[dict[str, Any]]:
    df = _fetch_ohlcv(ticker, days=days)
    if df.empty or len(df) < 60:
        return None

    df_ind = _calc_all_indicators(df)
    tech_info = get_signal_summary(df_ind)
    tech_score = float(tech_info.get("score", 0.0))
    mom_score = float(_momentum_score(df))
    vol_score = float(_volume_score(df))
    vol_penalty = float(_volatility_penalty(df))
    trend_score = float(_trend_consistency_score(df))

    close = _series_from_column(df, "Close").dropna()
    if len(close) < 60:
        return None

    returns_60 = close.pct_change().dropna().tail(60)
    annual_return = float(returns_60.mean() * 252) if len(returns_60) >= 20 else 0.0
    annual_vol = float(returns_60.std() * np.sqrt(252)) if len(returns_60) >= 20 else 0.0
    risk_adjusted_return = annual_return / annual_vol if annual_vol > 0 else 0.0

    risk_score = float(np.clip(risk_adjusted_return * 22 + vol_penalty, -100, 100))
    momentum_score = float(np.clip(mom_score * 2.5, -100, 100))
    volume_score = float(np.clip(vol_score * 5.0, -100, 100))
    trend_quality_score = float(np.clip(trend_score * 6.0, -100, 100))

    return {
        "ticker": ticker,
        "name": _get_ticker_name(ticker),
        "current_price": int(close.iloc[-1]),
        "tech_score": tech_score,
        "mom_score": mom_score,
        "vol_score": vol_score,
        "trend_score": trend_score,
        "risk_adjusted_return": risk_adjusted_return,
        "momentum_score_norm": momentum_score,
        "volume_score_norm": volume_score,
        "trend_quality_score_norm": trend_quality_score,
        "risk_score_norm": risk_score,
    }


@lru_cache(maxsize=128)
def _holdings_returns_cache(holdings_key: tuple[str, ...], days: int = 120) -> dict[str, pd.Series]:
    returns_map: dict[str, pd.Series] = {}
    for ticker in holdings_key:
        returns = _get_returns_series(ticker, days=days)
        if len(returns) >= 20:
            returns_map[ticker] = returns
    return returns_map


def _diversification_metrics(candidate_returns: pd.Series, holdings_returns: dict[str, pd.Series]) -> tuple[float, float, float]:
    if candidate_returns.empty or not holdings_returns:
        return 0.0, 0.0, 0.0

    corr_values: list[float] = []
    for holding_returns in holdings_returns.values():
        merged = pd.concat(
            [candidate_returns.rename("candidate"), holding_returns.rename("holding")],
            axis=1,
            join="inner",
        ).dropna()
        if len(merged) < 20:
            continue
        candidate_aligned = pd.Series(merged.iloc[:, 0], dtype=float)
        holding_aligned = pd.Series(merged.iloc[:, 1], dtype=float)
        if len(candidate_aligned) < 2 or len(holding_aligned) < 2:
            continue

        pair_df = pd.DataFrame({"candidate": candidate_aligned, "holding": holding_aligned}).dropna()
        if len(pair_df) < 2:
            continue

        corr_matrix = pair_df.corr()
        corr_val = float(corr_matrix.iloc[0, 1]) if corr_matrix.shape == (2, 2) else float("nan")
        if np.isfinite(corr_val):
            corr_values.append(corr_val)

    if not corr_values:
        return 0.0, 0.0, 0.0

    avg_corr = float(np.mean(corr_values))
    diversification_effect = float(1.0 - avg_corr)
    diversification_score = float(np.clip((0.3 - avg_corr) * 100, -100, 100))
    return diversification_score, diversification_effect, avg_corr


def _portfolio_recommend_grade(total_score: float) -> str:
    if total_score >= 45:
        return "A+"
    if total_score >= 30:
        return "A"
    if total_score >= 15:
        return "B+"
    if total_score >= 0:
        return "B"
    if total_score >= -15:
        return "C"
    return "D"


def _portfolio_reason(
    has_holdings: bool,
    avg_corr: float,
    risk_adjusted_return: float,
    tech_score: float,
    mom_score: float,
    trend_score: float,
) -> str:
    reasons = []
    if has_holdings:
        if avg_corr <= 0.1:
            reasons.append("기존 보유종목과 낮은 상관관계로 분산 효과 극대화")
        elif avg_corr <= 0.3:
            reasons.append("보유 포트폴리오와 상관관계가 낮아 리스크 분산에 유리")

    if risk_adjusted_return >= 1.0:
        reasons.append("최근 60일 리스크 대비 수익률이 우수")
    elif risk_adjusted_return >= 0.5:
        reasons.append("변동성 대비 수익 흐름이 안정적")

    if tech_score >= 20:
        reasons.append("기술지표가 매수 우위 신호를 유지")
    if mom_score >= 10:
        reasons.append("단기·중기 모멘텀이 동반 상승")
    if trend_score >= 8:
        reasons.append("상승 추세의 일관성이 높음")

    if not reasons:
        if has_holdings:
            return "포트폴리오 보완 관점에서 점진적 비중 확대 후보"
        return "시장 내 상대강도와 추세가 균형적으로 양호"

    return " / ".join(reasons[:2])


def recommend_for_portfolio(holdings_tickers: list[str], market: str = "KOSPI", top_n: int = 10) -> pd.DataFrame:
    market_key = (market or "KOSPI").upper()
    if market_key not in {"KOSPI", "KOSDAQ"}:
        market_key = "KOSPI"

    result_columns = [
        "종목코드",
        "종목명",
        "현재가",
        "종합점수",
        "추천등급",
        "분산효과",
        "리스크조정수익률",
        "기술점수",
        "모멘텀",
        "추천사유",
    ]

    target_count = max(1, int(top_n))
    clean_holdings = tuple(sorted({str(t).strip() for t in holdings_tickers if str(t).strip()}))
    holdings_set = set(clean_holdings)
    has_holdings = len(holdings_set) > 0

    today = datetime.now()
    market_tickers: list[str] = []
    for offset in range(7):
        probe = (today - timedelta(days=offset)).strftime("%Y%m%d")
        market_tickers = [str(ticker) for ticker in krx.get_market_ticker_list(probe, market=market_key)]
        if market_tickers:
            break

    if not market_tickers:
        return _empty_dataframe_with_columns(result_columns)

    candidates = [ticker for ticker in market_tickers if ticker not in holdings_set]
    if not candidates:
        return _empty_dataframe_with_columns(result_columns)

    candidate_pool = candidates
    holdings_returns = _holdings_returns_cache(clean_holdings, days=120) if has_holdings else {}

    results: list[dict[str, Any]] = []
    for ticker in candidate_pool:
        try:
            snapshot = _candidate_factor_snapshot(ticker, days=120)
            if not snapshot:
                continue

            candidate_returns = _get_returns_series(ticker, days=120)
            div_score, diversification_effect, avg_corr = _diversification_metrics(candidate_returns, holdings_returns)

            total_score = (
                snapshot["tech_score"] * 0.25
                + snapshot["momentum_score_norm"] * 0.20
                + snapshot["volume_score_norm"] * 0.10
                + div_score * 0.20
                + snapshot["risk_score_norm"] * 0.15
                + snapshot["trend_quality_score_norm"] * 0.10
            )
            total_score = float(np.clip(total_score, -100, 100))

            reason = _portfolio_reason(
                has_holdings=has_holdings,
                avg_corr=avg_corr,
                risk_adjusted_return=float(snapshot["risk_adjusted_return"]),
                tech_score=float(snapshot["tech_score"]),
                mom_score=float(snapshot["mom_score"]),
                trend_score=float(snapshot["trend_score"]),
            )

            results.append(
                {
                    "종목코드": ticker,
                    "종목명": snapshot["name"],
                    "현재가": int(snapshot["current_price"]),
                    "종합점수": round(total_score, 1),
                    "추천등급": _portfolio_recommend_grade(total_score),
                    "분산효과": round(diversification_effect, 3) if has_holdings else 0.0,
                    "리스크조정수익률": round(float(snapshot["risk_adjusted_return"]), 3),
                    "기술점수": round(float(snapshot["tech_score"]), 1),
                    "모멘텀": round(float(snapshot["mom_score"]), 1),
                    "추천사유": reason,
                }
            )
        except Exception:
            continue

    if not results:
        return _empty_dataframe_with_columns(result_columns)

    result_df = pd.DataFrame(results).sort_values("종합점수", ascending=False).head(target_count)
    result_df = pd.DataFrame(result_df.loc[:, result_columns]).reset_index(drop=True)
    result_df.index = result_df.index + 1
    return cast(pd.DataFrame, result_df)


def recommend_stocks(
    market: str = "KOSPI",
    top_n: int = 50,
    result_count: int = 20,
) -> pd.DataFrame:
    tickers = _get_recent_market_tickers(market)[:top_n]
    if not tickers:
        return pd.DataFrame()

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
    tickers = _get_recent_market_tickers(market)[:top_n]
    if not tickers:
        return pd.DataFrame()

    results = []
    backup_results: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            name = krx.get_market_ticker_name(ticker)
            df = _fetch_ohlcv(ticker, days=120)
            if df.empty or len(df) < 30:
                continue

            close = _series_from_column(df, "Close").dropna()
            volume = _series_from_column(df, "Volume").fillna(0)
            if len(close) < 30:
                continue

            returns = close.pct_change().dropna()
            if len(returns) < 20:
                continue

            daily_vol = float(returns.tail(20).std() * np.sqrt(252) * 100)
            ret_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0
            ret_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
            ret_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else 0.0

            vol_ma_raw = volume.rolling(20).mean()
            vol_ma = vol_ma_raw if isinstance(vol_ma_raw, pd.Series) else pd.Series(vol_ma_raw, dtype=float)
            avg_vol_20 = float(vol_ma.iloc[-1]) if len(vol_ma) >= 20 else 0.0
            vol_ratio = float(volume.iloc[-1] / avg_vol_20) if avg_vol_20 > 0 else 0

            df_ind = _calc_all_indicators(df)
            rsi_series = _series_from_column(df_ind, "RSI").dropna() if "RSI" in df_ind.columns else pd.Series(dtype=float)
            rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

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

            max_gain_20 = float(returns.tail(20).max() * 100) if len(returns) >= 20 else 0
            max_loss_20 = float(returns.tail(20).min() * 100) if len(returns) >= 20 else 0

            if total >= 40:
                risk_label = "🔥🔥🔥 초고위험"
            elif total >= 25:
                risk_label = "🔥🔥 고위험"
            else:
                risk_label = "🔥 위험"

            row_payload = {
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
            }
            backup_results.append(row_payload)

            if total < 10:
                continue

            results.append(row_payload)
        except Exception:
            continue

    if not results:
        if not backup_results:
            return pd.DataFrame()
        backup_df = pd.DataFrame(backup_results).sort_values("공격점수", ascending=False).head(result_count)
        backup_df = backup_df.reset_index(drop=True)
        backup_df.index = backup_df.index + 1
        return backup_df

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("공격점수", ascending=False).head(result_count)
    result_df = result_df.reset_index(drop=True)
    result_df.index = result_df.index + 1
    return result_df


def learn_optimal_weights(
    market: str = "KOSPI",
    lookback_days: int = 60,
    top_n: int = 50,
) -> dict[str, Any]:
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

    tickers: list[str] = []
    for offset in range(10):
        probe = (eval_date - timedelta(days=offset)).strftime("%Y%m%d")
        tickers = [str(ticker) for ticker in krx.get_market_ticker_list(probe, market=market)]
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

    samples: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            raw_ohlcv = krx.get_market_ohlcv(start_str, end_str, ticker)
            if raw_ohlcv.empty:
                continue

            renamed = raw_ohlcv.rename(columns={
                "시가": "Open", "고가": "High", "저가": "Low",
                "종가": "Close", "거래량": "Volume"
            })
            df = pd.DataFrame(renamed[["Open", "High", "Low", "Close", "Volume"]].copy())
            if len(df) < 90:
                continue

            past_df = pd.DataFrame(df[df.index <= eval_date].copy())
            future_df = pd.DataFrame(df[df.index > eval_date].copy())
            if len(past_df) < 60 or len(future_df) == 0:
                continue

            ind_df = _calc_all_indicators(past_df)
            tech_info = get_signal_summary(ind_df)

            past_close = _series_from_column(past_df, "Close").dropna()
            future_close = _series_from_column(future_df, "Close").dropna()
            if past_close.empty or future_close.empty:
                continue

            close_past = float(past_close.iloc[-1])
            close_now = float(future_close.iloc[-1])
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

    def evaluate(weights: dict[str, float]) -> dict[str, Any]:
        score = (
            _series_from_column(sample_df, "tech_score") * weights["tech_w"]
            + _series_from_column(sample_df, "mom_score") * weights["mom_w"]
            + _series_from_column(sample_df, "vol_score") * weights["vol_w"]
            + _series_from_column(sample_df, "trend_score") * weights["trend_w"]
            + _series_from_column(sample_df, "vol_penalty") * weights["vol_penalty_w"]
        )

        ranked = pd.DataFrame(sample_df.assign(pred_score=score)).sort_values("pred_score", ascending=False)
        top_return_series = _series_from_column(ranked.head(top_bucket), "future_return")
        top_return = float(top_return_series.mean()) if not top_return_series.empty else 0.0

        corr = 0.0
        aligned = pd.concat(
            [
                _series_from_column(ranked, "pred_score").rename("pred"),
                _series_from_column(ranked, "future_return").rename("future"),
            ],
            axis=1,
            join="inner",
        ).dropna()
        if len(aligned) >= 2:
            corr_matrix = np.corrcoef(
                aligned["pred"].to_numpy(dtype=float),
                aligned["future"].to_numpy(dtype=float),
            )
            if corr_matrix.shape == (2, 2):
                corr = float(corr_matrix[0, 1])
                if not np.isfinite(corr):
                    corr = 0.0

        return {
            "weights": weights,
            "top_return": round(top_return, 4),
            "corr": round(corr, 4),
        }

    combo_results: list[dict[str, Any]] = []
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
