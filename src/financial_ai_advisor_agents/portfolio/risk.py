from collections.abc import Sequence

import numpy as np

from financial_ai_advisor_agents.schemas.portfolio import RiskMetrics


def cumulative_max_drawdown(returns: Sequence[float]) -> float:
    values = np.asarray(returns, dtype=float)
    if values.size == 0:
        raise ValueError("at least one portfolio return is required")
    wealth = np.cumprod(1.0 + values)
    running_peak = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    return float(max(0.0, -np.min(wealth / running_peak - 1.0)))


def historical_var_95(returns: Sequence[float]) -> float:
    values = np.asarray(returns, dtype=float)
    if values.size == 0:
        raise ValueError("at least one portfolio return is required")
    return float(max(0.0, -np.percentile(values, 5)))


def calculate_risk(
    portfolio_returns: Sequence[float],
    weights: Sequence[float],
    sector_weights: Sequence[float],
    periods_per_year: int = 12,
) -> RiskMetrics:
    returns = np.asarray(portfolio_returns, dtype=float)
    weight_array = np.asarray(weights, dtype=float)
    sector_array = np.asarray(sector_weights, dtype=float)
    if returns.size == 0 or weight_array.size == 0 or sector_array.size == 0:
        raise ValueError("returns, holding weights and sector weights are required")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")

    volatility = float(returns.std(ddof=1) * np.sqrt(periods_per_year)) if returns.size > 1 else 0.0
    drawdown = cumulative_max_drawdown(returns)
    var_95 = historical_var_95(returns)
    hhi = float(np.square(weight_array).sum())
    max_weight = float(weight_array.max())
    max_sector_weight = float(sector_array.max())
    components = (
        30.0 * min(volatility / 0.40, 1.0),
        25.0 * min(drawdown / 0.50, 1.0),
        15.0 * min(var_95 / 0.10, 1.0),
        10.0 * min(hhi / 0.50, 1.0),
        10.0 * min(max_weight / 0.50, 1.0),
        10.0 * min(max_sector_weight / 0.70, 1.0),
    )
    score = float(np.clip(sum(components), 0.0, 100.0))
    level = "低" if score < 25 else "中" if score < 50 else "高" if score < 75 else "极高"
    return RiskMetrics(
        score=score,
        level=level,
        annualized_volatility=volatility,
        max_drawdown=drawdown,
        var_95=var_95,
        hhi=hhi,
        max_weight=max_weight,
        max_sector_weight=max_sector_weight,
    )
