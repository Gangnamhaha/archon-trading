"""
고급 리스크 분석 모듈
- VaR (Value at Risk)
- Sortino 비율
- Beta, Alpha
- 효율적 프론티어 (Markowitz 포트폴리오 최적화)
- 최대 낙폭 분석
"""
import pandas as pd
import numpy as np
from scipy.optimize import minimize


def calc_var(returns: pd.Series, confidence: float = 0.95, method: str = "historical") -> dict:
    """
    VaR (Value at Risk) 계산
    - historical: 과거 데이터 기반
    - parametric: 정규분포 가정
    """
    returns = returns.dropna()
    if len(returns) < 10:
        return {"VaR": 0, "CVaR": 0, "method": method}

    if method == "historical":
        var = np.percentile(returns, (1 - confidence) * 100)
        cvar = returns[returns <= var].mean()
    else:  # parametric
        mu = returns.mean()
        sigma = returns.std()
        from scipy.stats import norm
        z = norm.ppf(1 - confidence)
        var = mu + z * sigma
        cvar = mu - sigma * norm.pdf(z) / (1 - confidence)

    return {
        "VaR": round(float(var) * 100, 4),
        "CVaR": round(float(cvar) * 100, 4) if not np.isnan(cvar) else 0,
        "confidence": confidence,
        "method": method,
    }


def calc_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.03, target: float = 0) -> float:
    """Sortino 비율 (하방 위험만 고려)"""
    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free_rate / 252
    downside = returns[returns < target]
    if len(downside) < 1 or downside.std() == 0:
        return 0.0
    downside_std = downside.std() * np.sqrt(252)
    annual_return = excess.mean() * 252
    return round(float(annual_return / downside_std), 4)


def calc_beta_alpha(stock_returns: pd.Series, market_returns: pd.Series, risk_free_rate: float = 0.03) -> dict:
    """Beta, Alpha 계산 (CAPM)"""
    aligned = pd.DataFrame({"stock": stock_returns, "market": market_returns}).dropna()
    if len(aligned) < 10:
        return {"beta": 0, "alpha": 0, "r_squared": 0}

    cov = aligned.cov()
    beta = cov.loc["stock", "market"] / cov.loc["market", "market"]
    rf_daily = risk_free_rate / 252
    stock_annual = aligned["stock"].mean() * 252
    market_annual = aligned["market"].mean() * 252
    alpha = stock_annual - (rf_daily * 252 + beta * (market_annual - rf_daily * 252))

    correlation = aligned.corr().loc["stock", "market"]

    return {
        "beta": round(float(beta), 4),
        "alpha": round(float(alpha) * 100, 4),
        "r_squared": round(float(correlation ** 2), 4),
        "correlation": round(float(correlation), 4),
    }


def calc_max_drawdown_detail(equity: pd.Series) -> dict:
    """최대 낙폭 상세 분석"""
    if len(equity) < 2:
        return {}

    series = pd.Series(equity, dtype=float)
    rolling_max = series.cummax()
    drawdown = (series - rolling_max) / rolling_max

    mdd = float(drawdown.min())
    mdd_end_pos = int(drawdown.to_numpy().argmin())
    mdd_end_idx = drawdown.index[mdd_end_pos]

    pre_peak = series.iloc[: mdd_end_pos + 1]
    mdd_start_pos = int(pre_peak.to_numpy().argmax())
    mdd_start_idx = pre_peak.index[mdd_start_pos]

    # 회복일
    recovery = series.iloc[mdd_end_pos:]
    recovery_target = float(rolling_max.iloc[mdd_end_pos])
    recovery_hits = recovery[recovery >= recovery_target]
    recovery_date = recovery_hits.index[0] if not recovery_hits.empty else None

    if isinstance(mdd_end_idx, pd.Timestamp) and isinstance(mdd_start_idx, pd.Timestamp):
        drawdown_days = int((mdd_end_idx - mdd_start_idx).days)
    else:
        drawdown_days = int(mdd_end_pos - mdd_start_pos)

    return {
        "MDD (%)": round(float(mdd) * 100, 2),
        "시작일": str(mdd_start_idx),
        "최저점": str(mdd_end_idx),
        "회복일": str(recovery_date) if recovery_date else "미회복",
        "낙폭 기간(일)": drawdown_days,
        "drawdown_series": drawdown,
    }


def calc_risk_metrics(returns: pd.Series, risk_free_rate: float = 0.03) -> dict:
    """종합 리스크 지표"""
    returns = returns.dropna()
    if len(returns) < 10:
        return {}

    annual_return = returns.mean() * 252
    annual_vol = returns.std() * np.sqrt(252)
    sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
    sortino = calc_sortino_ratio(returns, risk_free_rate)
    var_95 = calc_var(returns, 0.95)
    var_99 = calc_var(returns, 0.99)

    return {
        "연간 수익률 (%)": round(float(annual_return) * 100, 2),
        "연간 변동성 (%)": round(float(annual_vol) * 100, 2),
        "샤프 비율": round(float(sharpe), 4),
        "소르티노 비율": sortino,
        "VaR 95% (%)": var_95["VaR"],
        "CVaR 95% (%)": var_95["CVaR"],
        "VaR 99% (%)": var_99["VaR"],
        "CVaR 99% (%)": var_99["CVaR"],
        "최대 일일 손실 (%)": round(float(returns.min()) * 100, 2),
        "최대 일일 이익 (%)": round(float(returns.max()) * 100, 2),
        "양의 일 비율 (%)": round(float((returns > 0).sum() / len(returns)) * 100, 2),
        "왜도 (Skewness)": round(float(returns.skew()), 4),
        "첨도 (Kurtosis)": round(float(returns.kurtosis()), 4),
    }


# ============================
# 효율적 프론티어 (Markowitz)
# ============================

def calc_efficient_frontier(returns_df: pd.DataFrame, num_portfolios: int = 5000,
                            risk_free_rate: float = 0.03) -> dict:
    """
    효율적 프론티어 계산 (Markowitz 포트폴리오 최적화)
    returns_df: 각 컬럼이 종목별 일별 수익률인 DataFrame
    """
    returns_df = returns_df.dropna()
    if returns_df.shape[1] < 2 or len(returns_df) < 30:
        return {"error": "최소 2개 종목, 30일 데이터 필요"}

    n_assets = returns_df.shape[1]
    mean_returns = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252

    # 랜덤 포트폴리오 생성
    results = np.zeros((3, num_portfolios))
    weights_record = []

    for i in range(num_portfolios):
        weights = np.random.random(n_assets)
        weights /= weights.sum()
        weights_record.append(weights)

        port_return = np.dot(weights, mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = (port_return - risk_free_rate) / port_vol

        results[0, i] = port_vol * 100   # 변동성 (%)
        results[1, i] = port_return * 100  # 수익률 (%)
        results[2, i] = sharpe

    # 최적 포트폴리오
    max_sharpe_idx = results[2].argmax()
    min_vol_idx = results[0].argmin()

    # 최적화 (최대 샤프)
    def neg_sharpe(weights):
        port_return = np.dot(weights, mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return -(port_return - risk_free_rate) / port_vol

    constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
    bounds = tuple((0, 1) for _ in range(n_assets))
    init_weights = np.array([1.0 / n_assets] * n_assets)

    opt_sharpe = minimize(neg_sharpe, init_weights, method="SLSQP", bounds=bounds, constraints=constraints)

    # 최소 변동성
    def portfolio_vol(weights):
        return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

    opt_min_vol = minimize(portfolio_vol, init_weights, method="SLSQP", bounds=bounds, constraints=constraints)

    return {
        "volatility": results[0],
        "returns": results[1],
        "sharpe": results[2],
        "tickers": list(returns_df.columns),
        "max_sharpe_weights": dict(zip(returns_df.columns, np.round(opt_sharpe.x * 100, 2))),
        "max_sharpe_return": round(float(np.dot(opt_sharpe.x, mean_returns)) * 100, 2),
        "max_sharpe_vol": round(float(np.sqrt(np.dot(opt_sharpe.x.T, np.dot(cov_matrix, opt_sharpe.x)))) * 100, 2),
        "min_vol_weights": dict(zip(returns_df.columns, np.round(opt_min_vol.x * 100, 2))),
        "min_vol_return": round(float(np.dot(opt_min_vol.x, mean_returns)) * 100, 2),
        "min_vol_vol": round(float(np.sqrt(np.dot(opt_min_vol.x.T, np.dot(cov_matrix, opt_min_vol.x)))) * 100, 2),
    }
