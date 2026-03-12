"""
포트폴리오 트래커 모듈
- 보유 종목 관리
- 수익률 계산
- 자산 배분 분석
"""
import pandas as pd
from data.database import add_stock, remove_stock, get_portfolio, add_trade
from data.fetcher import fetch_stock


class PortfolioTracker:
    """포트폴리오 추적 관리자"""

    def __init__(self):
        self.portfolio_df = get_portfolio()

    def refresh(self):
        """포트폴리오 데이터 새로고침"""
        self.portfolio_df = get_portfolio()

    def add_holding(self, ticker: str, market: str, name: str,
                    buy_price: float, quantity: int, buy_date: str = None):
        """종목 추가"""
        add_stock(ticker, market, name, buy_price, quantity, buy_date)
        add_trade(ticker, market, "BUY", buy_price, quantity, "수동 추가")
        self.refresh()

    def remove_holding(self, stock_id: int):
        """종목 삭제"""
        remove_stock(stock_id)
        self.refresh()

    def get_holdings(self) -> pd.DataFrame:
        """전체 보유 종목 조회 (현재가 포함)"""
        self.refresh()
        if self.portfolio_df.empty:
            return pd.DataFrame()

        holdings = self.portfolio_df.copy()
        current_prices = []
        returns = []
        eval_amounts = []

        for _, row in holdings.iterrows():
            try:
                df = fetch_stock(row["ticker"], row["market"], "5d")
                if not df.empty:
                    current_price = df["Close"].iloc[-1]
                else:
                    current_price = row["buy_price"]
            except Exception:
                current_price = row["buy_price"]

            current_prices.append(current_price)
            ret = (current_price - row["buy_price"]) / row["buy_price"] * 100
            returns.append(round(ret, 2))
            eval_amounts.append(round(current_price * row["quantity"], 0))

        holdings["현재가"] = current_prices
        holdings["수익률(%)"] = returns
        holdings["평가금액"] = eval_amounts
        holdings["매수금액"] = holdings["buy_price"] * holdings["quantity"]
        holdings["평가손익"] = holdings["평가금액"] - holdings["매수금액"]

        return holdings

    def get_total_value(self) -> dict:
        """총 평가 금액 및 수익률 계산"""
        holdings = self.get_holdings()
        if holdings.empty:
            return {
                "총매수금액": 0,
                "총평가금액": 0,
                "총평가손익": 0,
                "총수익률": 0,
                "종목수": 0,
            }

        total_buy = holdings["매수금액"].sum()
        total_eval = holdings["평가금액"].sum()
        total_pnl = total_eval - total_buy
        total_return = (total_pnl / total_buy * 100) if total_buy > 0 else 0

        return {
            "총매수금액": round(total_buy, 0),
            "총평가금액": round(total_eval, 0),
            "총평가손익": round(total_pnl, 0),
            "총수익률": round(total_return, 2),
            "종목수": len(holdings),
        }

    def get_allocation(self) -> pd.DataFrame:
        """자산 배분 비율"""
        holdings = self.get_holdings()
        if holdings.empty:
            return pd.DataFrame()

        total = holdings["평가금액"].sum()
        alloc = holdings[["name", "ticker", "평가금액"]].copy()
        alloc["비율(%)"] = round(alloc["평가금액"] / total * 100, 2) if total > 0 else 0
        return alloc.sort_values("비율(%)", ascending=False)
