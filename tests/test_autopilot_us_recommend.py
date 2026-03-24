import pandas as pd

from pages import util_ap_us


def _mock_us_df(last_close: float, trend: float) -> pd.DataFrame:
    close = [last_close * (1 + trend * i / 30.0) for i in range(30)]
    volume = [1_000_000 + (i * 10_000) for i in range(30)]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [v * 1.01 for v in close],
            "Low": [v * 0.99 for v in close],
            "Close": close,
            "Volume": volume,
        }
    )


def test_recommend_us_returns_non_empty(monkeypatch):
    monkeypatch.setattr(
        util_ap_us,
        "get_us_popular_stocks",
        lambda: pd.DataFrame(
            [
                {"ticker": "AAPL", "name": "Apple"},
                {"ticker": "MSFT", "name": "Microsoft"},
            ]
        ),
    )

    def _fake_fetch_stock(ticker: str, market: str, period: str, interval: str) -> pd.DataFrame:
        assert market == "US"
        return _mock_us_df(100.0 if ticker == "AAPL" else 200.0, 0.08 if ticker == "AAPL" else 0.03)

    monkeypatch.setattr(util_ap_us, "fetch_stock", _fake_fetch_stock)

    out = util_ap_us.recommend_us(mode="일반 추천", max_stocks=2)
    assert not out.empty
    assert len(out) == 2
    assert {"종목코드", "종목명", "현재가", "점수"}.issubset(set(out.columns))


def test_recommend_us_aggressive_mode(monkeypatch):
    monkeypatch.setattr(
        util_ap_us,
        "get_us_popular_stocks",
        lambda: pd.DataFrame(
            [
                {"ticker": "TSLA", "name": "Tesla"},
                {"ticker": "NVDA", "name": "NVIDIA"},
            ]
        ),
    )

    def _fake_fetch_stock(ticker: str, market: str, period: str, interval: str) -> pd.DataFrame:
        assert market == "US"
        return _mock_us_df(300.0 if ticker == "TSLA" else 500.0, 0.12 if ticker == "TSLA" else 0.06)

    monkeypatch.setattr(util_ap_us, "fetch_stock", _fake_fetch_stock)

    out = util_ap_us.recommend_us(mode="🔥 공격적 추천", max_stocks=1)
    assert not out.empty
    assert len(out) == 1
    assert out.iloc[0]["종목코드"] in {"TSLA", "NVDA"}
