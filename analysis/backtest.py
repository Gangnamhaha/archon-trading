"""
백테스팅 엔진 모듈
- 과거 데이터 기반 투자 전략 테스트
- 수익률, MDD, 샤프비율 등 성과 지표 계산
"""
import pandas as pd
import numpy as np
from analysis.technical import calc_sma, calc_rsi, calc_macd, calc_bollinger


class BacktestEngine:
    """백테스팅 엔진"""

    def __init__(self, df: pd.DataFrame, initial_capital: float = 10_000_000, commission: float = 0.00015):
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.commission = commission
        self.trades = []
        self.equity_curve = []
        self.results = {}

    def run(self, signals: pd.Series) -> dict:
        """
        시그널 시리즈를 받아 백테스트 실행
        signals: 1 = 매수, -1 = 매도, 0 = 관망
        """
        capital = self.initial_capital
        position = 0  # 보유 수량
        buy_price = 0
        self.trades = []
        equity = []

        for i in range(len(self.df)):
            date = self.df.index[i]
            price = self.df["Close"].iloc[i]
            signal = signals.iloc[i] if i < len(signals) else 0

            if signal == 1 and position == 0:
                # 매수: 전액 투자
                quantity = int(capital / (price * (1 + self.commission)))
                if quantity > 0:
                    cost = quantity * price * (1 + self.commission)
                    capital -= cost
                    position = quantity
                    buy_price = price
                    self.trades.append({
                        "date": date, "action": "BUY",
                        "price": price, "quantity": quantity,
                        "capital": capital
                    })

            elif signal == -1 and position > 0:
                # 매도: 전량 매도
                revenue = position * price * (1 - self.commission)
                pnl = revenue - (position * buy_price)
                capital += revenue
                self.trades.append({
                    "date": date, "action": "SELL",
                    "price": price, "quantity": position,
                    "pnl": pnl, "capital": capital
                })
                position = 0
                buy_price = 0

            # 현재 자산 가치
            total_value = capital + (position * price)
            equity.append({"date": date, "equity": total_value, "capital": capital, "position_value": position * price})

        self.equity_curve = pd.DataFrame(equity).set_index("date")
        self._calc_results()
        return self.results

    def _calc_results(self):
        """성과 지표 계산"""
        if self.equity_curve.empty:
            self.results = {}
            return

        eq = self.equity_curve["equity"]
        total_return = (eq.iloc[-1] / self.initial_capital - 1) * 100
        days = (eq.index[-1] - eq.index[0]).days
        annual_return = ((eq.iloc[-1] / self.initial_capital) ** (365 / max(days, 1)) - 1) * 100 if days > 0 else 0

        # MDD (최대 낙폭)
        rolling_max = eq.cummax()
        drawdown = (eq - rolling_max) / rolling_max * 100
        mdd = drawdown.min()

        # 샤프 비율 (무위험 수익률 3% 가정)
        daily_returns = eq.pct_change().dropna()
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe = (daily_returns.mean() - 0.03 / 252) / daily_returns.std() * np.sqrt(252)
        else:
            sharpe = 0

        # 소르티노 비율 (하방 변동성만 고려)
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino = (daily_returns.mean() - 0.03 / 252) / downside.std() * np.sqrt(252)
        else:
            sortino = 0

        # 칼마 비율 (연환산 수익률 / MDD)
        calmar = abs(annual_return / mdd) if mdd != 0 else 0

        # 평균 수익/손실
        sell_trades = [t for t in self.trades if t["action"] == "SELL"]
        wins = [t.get("pnl", 0) for t in sell_trades if t.get("pnl", 0) > 0]
        losses = [t.get("pnl", 0) for t in sell_trades if t.get("pnl", 0) < 0]
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0
        win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0

        self.results = {
            "총 수익률 (%)": round(total_return, 2),
            "연환산 수익률 (%)": round(annual_return, 2),
            "최대 낙폭 MDD (%)": round(mdd, 2),
            "샤프 비율": round(sharpe, 2),
            "소르티노 비율": round(sortino, 2),
            "칼마 비율": round(calmar, 2),
            "총 거래 횟수": len(self.trades),
            "매수 횟수": sum(1 for t in self.trades if t["action"] == "BUY"),
            "매도 횟수": len(sell_trades),
            "승률 (%)": round(win_rate, 2),
            "평균 수익": round(avg_win, 0),
            "평균 손실": round(avg_loss, 0),
            "손익비 (Profit Factor)": round(profit_factor, 2),
            "최종 자산": round(self.equity_curve["equity"].iloc[-1], 0),
            "초기 자본": self.initial_capital,
        }

    def get_results(self) -> dict:
        return self.results

    def get_equity_curve(self) -> pd.DataFrame:
        return self.equity_curve

    def get_trades(self) -> pd.DataFrame:
        return pd.DataFrame(self.trades)


# === 내장 전략 함수들 ===

def golden_cross_strategy(df: pd.DataFrame, short: int = 5, long: int = 20) -> pd.Series:
    """골든크로스/데드크로스 전략"""
    data = calc_sma(df, [short, long])
    sma_short = data[f"SMA_{short}"]
    sma_long = data[f"SMA_{long}"]

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(sma_short.iloc[i]) or pd.isna(sma_long.iloc[i]):
            continue
        if pd.isna(sma_short.iloc[i - 1]) or pd.isna(sma_long.iloc[i - 1]):
            continue
        # 골든크로스: 단기 MA가 장기 MA를 상향 돌파
        if sma_short.iloc[i] > sma_long.iloc[i] and sma_short.iloc[i - 1] <= sma_long.iloc[i - 1]:
            signals.iloc[i] = 1
        # 데드크로스: 단기 MA가 장기 MA를 하향 돌파
        elif sma_short.iloc[i] < sma_long.iloc[i] and sma_short.iloc[i - 1] >= sma_long.iloc[i - 1]:
            signals.iloc[i] = -1

    return signals


def rsi_strategy(df: pd.DataFrame, buy_threshold: int = 30, sell_threshold: int = 70) -> pd.Series:
    """RSI 과매도/과매수 전략"""
    data = calc_rsi(df)
    rsi = data["RSI"]

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(rsi.iloc[i]) or pd.isna(rsi.iloc[i - 1]):
            continue
        # RSI가 과매도 구간에서 반등
        if rsi.iloc[i] > buy_threshold and rsi.iloc[i - 1] <= buy_threshold:
            signals.iloc[i] = 1
        # RSI가 과매수 구간에서 하락
        elif rsi.iloc[i] < sell_threshold and rsi.iloc[i - 1] >= sell_threshold:
            signals.iloc[i] = -1

    return signals


def macd_strategy(df: pd.DataFrame) -> pd.Series:
    """MACD 시그널 교차 전략"""
    data = calc_macd(df)
    macd = data["MACD"]
    signal = data["MACD_Signal"]

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(macd.iloc[i]) or pd.isna(signal.iloc[i]):
            continue
        if pd.isna(macd.iloc[i - 1]) or pd.isna(signal.iloc[i - 1]):
            continue
        # MACD가 시그널을 상향 돌파
        if macd.iloc[i] > signal.iloc[i] and macd.iloc[i - 1] <= signal.iloc[i - 1]:
            signals.iloc[i] = 1
        # MACD가 시그널을 하향 돌파
        elif macd.iloc[i] < signal.iloc[i] and macd.iloc[i - 1] >= signal.iloc[i - 1]:
            signals.iloc[i] = -1

    return signals


def bollinger_strategy(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """볼린저밴드 전략: 하단 매수, 상단 매도"""
    data = calc_bollinger(df, period, std_dev)

    signals = pd.Series(0, index=df.index)
    for i in range(1, len(df)):
        if pd.isna(data["BB_Lower"].iloc[i]) or pd.isna(data["BB_Upper"].iloc[i]):
            continue
        # 가격이 하단밴드 아래에서 위로 돌파 -> 매수
        if df["Close"].iloc[i] > data["BB_Lower"].iloc[i] and df["Close"].iloc[i - 1] <= data["BB_Lower"].iloc[i - 1]:
            signals.iloc[i] = 1
        # 가격이 상단밴드 위에서 아래로 돌파 -> 매도
        elif df["Close"].iloc[i] < data["BB_Upper"].iloc[i] and df["Close"].iloc[i - 1] >= data["BB_Upper"].iloc[i - 1]:
            signals.iloc[i] = -1

    return signals


# 전략 목록
STRATEGIES = {
    "골든크로스/데드크로스": golden_cross_strategy,
    "RSI 전략": rsi_strategy,
    "MACD 전략": macd_strategy,
    "볼린저밴드 전략": bollinger_strategy,
}
