"""
매매 전략 모듈
- 실시간 매매 시그널 생성
- 전략별 매수/매도 판단
"""
import pandas as pd
from abc import ABC, abstractmethod
from analysis.technical import calc_sma, calc_rsi, calc_macd, calc_bollinger


class TradingStrategy(ABC):
    """매매 전략 베이스 클래스"""

    def __init__(self, name: str = "기본 전략"):
        self.name = name
        self.params = {}

    @abstractmethod
    def get_signal(self, df: pd.DataFrame) -> str:
        """
        현재 시점의 매매 시그널 반환
        Returns: "BUY", "SELL", "HOLD"
        """
        pass

    def should_buy(self, df: pd.DataFrame) -> bool:
        return self.get_signal(df) == "BUY"

    def should_sell(self, df: pd.DataFrame) -> bool:
        return self.get_signal(df) == "SELL"

    def get_description(self) -> str:
        return f"{self.name}: {self.params}"


class GoldenCrossStrategy(TradingStrategy):
    """이동평균 골든크로스/데드크로스 전략"""

    def __init__(self, short_period: int = 5, long_period: int = 20):
        super().__init__("골든크로스 전략")
        self.short_period = short_period
        self.long_period = long_period
        self.params = {"단기 MA": short_period, "장기 MA": long_period}

    def get_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.long_period + 2:
            return "HOLD"

        data = calc_sma(df, [self.short_period, self.long_period])
        short_col = f"SMA_{self.short_period}"
        long_col = f"SMA_{self.long_period}"

        curr_short = data[short_col].iloc[-1]
        curr_long = data[long_col].iloc[-1]
        prev_short = data[short_col].iloc[-2]
        prev_long = data[long_col].iloc[-2]

        if pd.isna(curr_short) or pd.isna(curr_long):
            return "HOLD"

        if curr_short > curr_long and prev_short <= prev_long:
            return "BUY"
        elif curr_short < curr_long and prev_short >= prev_long:
            return "SELL"
        return "HOLD"


class RSIStrategy(TradingStrategy):
    """RSI 과매도/과매수 전략"""

    def __init__(self, period: int = 14, buy_threshold: int = 30, sell_threshold: int = 70):
        super().__init__("RSI 전략")
        self.period = period
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.params = {
            "RSI 기간": period,
            "매수 기준": f"RSI < {buy_threshold}",
            "매도 기준": f"RSI > {sell_threshold}",
        }

    def get_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.period + 2:
            return "HOLD"

        data = calc_rsi(df, self.period)
        curr_rsi = data["RSI"].iloc[-1]
        prev_rsi = data["RSI"].iloc[-2]

        if pd.isna(curr_rsi) or pd.isna(prev_rsi):
            return "HOLD"

        if curr_rsi > self.buy_threshold and prev_rsi <= self.buy_threshold:
            return "BUY"
        elif curr_rsi < self.sell_threshold and prev_rsi >= self.sell_threshold:
            return "SELL"
        return "HOLD"


class MACDStrategy(TradingStrategy):
    """MACD 시그널 교차 전략"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__("MACD 전략")
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.params = {"빠른선": fast, "느린선": slow, "시그널": signal}

    def get_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.slow + self.signal + 2:
            return "HOLD"

        data = calc_macd(df, self.fast, self.slow, self.signal)
        curr_macd = data["MACD"].iloc[-1]
        curr_signal = data["MACD_Signal"].iloc[-1]
        prev_macd = data["MACD"].iloc[-2]
        prev_signal = data["MACD_Signal"].iloc[-2]

        if pd.isna(curr_macd) or pd.isna(curr_signal):
            return "HOLD"

        if curr_macd > curr_signal and prev_macd <= prev_signal:
            return "BUY"
        elif curr_macd < curr_signal and prev_macd >= prev_signal:
            return "SELL"
        return "HOLD"


class BollingerStrategy(TradingStrategy):
    """볼린저밴드 전략"""

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__("볼린저밴드 전략")
        self.period = period
        self.std_dev = std_dev
        self.params = {"기간": period, "표준편차": std_dev}

    def get_signal(self, df: pd.DataFrame) -> str:
        if len(df) < self.period + 2:
            return "HOLD"

        data = calc_bollinger(df, self.period, self.std_dev)
        curr_close = df["Close"].iloc[-1]
        prev_close = df["Close"].iloc[-2]
        curr_lower = data["BB_Lower"].iloc[-1]
        curr_upper = data["BB_Upper"].iloc[-1]
        prev_lower = data["BB_Lower"].iloc[-2]
        prev_upper = data["BB_Upper"].iloc[-2]

        if pd.isna(curr_lower) or pd.isna(curr_upper):
            return "HOLD"

        # 하단밴드 아래에서 위로 돌파 -> 매수
        if curr_close > curr_lower and prev_close <= prev_lower:
            return "BUY"
        # 상단밴드 위에서 아래로 돌파 -> 매도
        elif curr_close < curr_upper and prev_close >= prev_upper:
            return "SELL"
        return "HOLD"


# 사용 가능한 전략 목록
AVAILABLE_STRATEGIES = {
    "골든크로스": GoldenCrossStrategy,
    "RSI": RSIStrategy,
    "MACD": MACDStrategy,
    "볼린저밴드": BollingerStrategy,
}
