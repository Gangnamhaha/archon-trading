import pandas as pd

from data.screener import screen_stocks


def test_screen_stocks_applies_return_20d_min_filter() -> None:
    df = pd.DataFrame(
        [
            {"종목코드": "000001", "1일수익률(%)": 1.0, "20일수익률(%)": 3.0, "RSI": 45, "MACD": 1.0, "MACD_Signal": 0.8, "SMA_5": 10, "SMA_20": 9, "거래량비율": 1.2},
            {"종목코드": "000002", "1일수익률(%)": 1.2, "20일수익률(%)": 7.0, "RSI": 50, "MACD": 1.1, "MACD_Signal": 1.0, "SMA_5": 12, "SMA_20": 10, "거래량비율": 1.0},
        ]
    )

    filtered = screen_stocks(df, {"return_20d_min": 5.0})

    assert len(filtered) == 1
    assert filtered.iloc[0]["종목코드"] == "000002"


def test_screen_stocks_applies_return_20d_max_filter() -> None:
    df = pd.DataFrame(
        [
            {"종목코드": "000001", "1일수익률(%)": -1.0, "20일수익률(%)": -8.0, "RSI": 30, "MACD": -0.5, "MACD_Signal": -0.2, "SMA_5": 9, "SMA_20": 10, "거래량비율": 0.8},
            {"종목코드": "000002", "1일수익률(%)": -0.5, "20일수익률(%)": -2.0, "RSI": 35, "MACD": -0.3, "MACD_Signal": -0.1, "SMA_5": 10, "SMA_20": 10, "거래량비율": 1.1},
        ]
    )

    filtered = screen_stocks(df, {"return_20d_max": -5.0})

    assert len(filtered) == 1
    assert filtered.iloc[0]["종목코드"] == "000001"
