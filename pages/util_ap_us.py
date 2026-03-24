from __future__ import annotations

from typing import Any

import pandas as pd

from data.fetcher import fetch_stock, get_us_popular_stocks


def _to_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "종목코드": pd.Series(dtype=str),
            "종목명": pd.Series(dtype=str),
            "현재가": pd.Series(dtype=float),
            "1일(%)": pd.Series(dtype=float),
            "5일(%)": pd.Series(dtype=float),
            "20일(%)": pd.Series(dtype=float),
            "변동성(%)": pd.Series(dtype=float),
            "거래량비율": pd.Series(dtype=float),
            "점수": pd.Series(dtype=float),
        }
    )


def recommend_us(mode: str = "일반 추천", max_stocks: int = 5) -> pd.DataFrame:
    universe = get_us_popular_stocks()
    if universe.empty or "ticker" not in universe.columns:
        return _to_dataframe()

    rows: list[dict[str, Any]] = []
    aggressive = "공격" in str(mode)

    for _, row in universe.iterrows():
        ticker = str(row.get("ticker") or "").strip().upper()
        name = str(row.get("name") or ticker)
        if not ticker:
            continue

        df = fetch_stock(ticker, "US", "6mo", "1d")
        if df.empty or "Close" not in df.columns or len(df) < 25:
            continue

        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(dtype=float)
        if close.empty:
            continue

        cur = float(close.iloc[-1])
        if cur <= 0:
            continue

        ret_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else 0.0
        ret_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) >= 6 else ret_1d
        ret_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else ret_5d
        volatility = float(close.pct_change().tail(20).std() * 100) if len(close) >= 21 else 0.0

        vol_ratio = 1.0
        if len(volume) >= 21:
            avg20 = float(volume.tail(20).mean())
            if avg20 > 0:
                vol_ratio = float(volume.iloc[-1] / avg20)

        if aggressive:
            score = (ret_5d * 0.35) + (ret_20d * 0.45) + (max(vol_ratio - 1.0, 0.0) * 10.0) - (volatility * 0.15)
        else:
            score = (ret_20d * 0.45) + (ret_5d * 0.2) - (volatility * 0.2) + (max(vol_ratio - 1.0, 0.0) * 5.0)

        rows.append(
            {
                "종목코드": ticker,
                "종목명": name,
                "현재가": round(cur, 2),
                "1일(%)": round(ret_1d, 2),
                "5일(%)": round(ret_5d, 2),
                "20일(%)": round(ret_20d, 2),
                "변동성(%)": round(volatility, 2),
                "거래량비율": round(vol_ratio, 2),
                "점수": round(float(score), 2),
            }
        )

    if not rows:
        return _to_dataframe()

    out = pd.DataFrame(rows).sort_values("점수", ascending=False).head(max(1, int(max_stocks))).reset_index(drop=True)
    out.index = out.index + 1
    return out
