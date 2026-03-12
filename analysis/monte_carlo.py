"""
몬테카를로 시뮬레이션 모듈
- 주가 경로 시뮬레이션 (GBM - Geometric Brownian Motion)
- 수익률 분포 예측
- 확률적 VaR
"""
import pandas as pd
import numpy as np


def run_monte_carlo(df: pd.DataFrame, num_simulations: int = 1000,
                    forecast_days: int = 30, confidence: float = 0.95) -> dict:
    """
    몬테카를로 시뮬레이션 실행
    GBM (기하 브라운 운동) 모델 기반
    """
    close = df["Close"].dropna()
    if len(close) < 30:
        return {"error": "최소 30일 데이터 필요"}

    log_returns = np.log(close / close.shift(1)).dropna()
    mu = log_returns.mean()
    sigma = log_returns.std()
    last_price = close.iloc[-1]

    # 시뮬레이션
    simulations = np.zeros((forecast_days, num_simulations))
    for i in range(num_simulations):
        daily_returns = np.random.normal(mu, sigma, forecast_days)
        price_path = last_price * np.exp(np.cumsum(daily_returns))
        simulations[:, i] = price_path

    # 최종 가격 분포
    final_prices = simulations[-1, :]
    mean_price = np.mean(final_prices)
    median_price = np.median(final_prices)

    # 신뢰 구간
    lower_bound = np.percentile(final_prices, (1 - confidence) / 2 * 100)
    upper_bound = np.percentile(final_prices, (1 + confidence) / 2 * 100)

    # 수익률 분포
    returns_dist = (final_prices / last_price - 1) * 100
    prob_profit = np.mean(final_prices > last_price) * 100
    prob_loss_10 = np.mean(final_prices < last_price * 0.9) * 100
    prob_gain_10 = np.mean(final_prices > last_price * 1.1) * 100

    # 백분위 가격 경로
    percentiles = {}
    for p in [5, 25, 50, 75, 95]:
        percentiles[f"p{p}"] = np.percentile(simulations, p, axis=1)

    return {
        "simulations": simulations,
        "final_prices": final_prices,
        "returns_dist": returns_dist,
        "current_price": float(last_price),
        "mean_price": round(float(mean_price), 0),
        "median_price": round(float(median_price), 0),
        "lower_bound": round(float(lower_bound), 0),
        "upper_bound": round(float(upper_bound), 0),
        "confidence": confidence,
        "forecast_days": forecast_days,
        "num_simulations": num_simulations,
        "prob_profit": round(float(prob_profit), 1),
        "prob_loss_10": round(float(prob_loss_10), 1),
        "prob_gain_10": round(float(prob_gain_10), 1),
        "expected_return": round(float(np.mean(returns_dist)), 2),
        "return_std": round(float(np.std(returns_dist)), 2),
        "best_case": round(float(np.max(final_prices)), 0),
        "worst_case": round(float(np.min(final_prices)), 0),
        "percentiles": percentiles,
        "mu": float(mu),
        "sigma": float(sigma),
    }


def run_portfolio_monte_carlo(returns_df: pd.DataFrame, weights: np.ndarray,
                               initial_capital: float = 10_000_000,
                               num_simulations: int = 1000,
                               forecast_days: int = 252) -> dict:
    """
    포트폴리오 몬테카를로 시뮬레이션
    """
    returns_df = returns_df.dropna()
    if len(returns_df) < 30:
        return {"error": "데이터 부족"}

    mean_returns = returns_df.mean().values
    cov_matrix = returns_df.cov().values
    portfolio_mean = np.dot(weights, mean_returns)
    portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

    simulations = np.zeros((forecast_days, num_simulations))
    for i in range(num_simulations):
        daily_returns = np.random.normal(portfolio_mean, portfolio_std, forecast_days)
        simulations[:, i] = initial_capital * np.exp(np.cumsum(daily_returns))

    final_values = simulations[-1, :]

    return {
        "simulations": simulations,
        "final_values": final_values,
        "initial_capital": initial_capital,
        "mean_value": round(float(np.mean(final_values)), 0),
        "median_value": round(float(np.median(final_values)), 0),
        "prob_profit": round(float(np.mean(final_values > initial_capital)) * 100, 1),
        "var_95": round(float(np.percentile(final_values, 5)), 0),
        "best_case": round(float(np.max(final_values)), 0),
        "worst_case": round(float(np.min(final_values)), 0),
        "expected_return_pct": round(float((np.mean(final_values) / initial_capital - 1) * 100), 2),
    }
