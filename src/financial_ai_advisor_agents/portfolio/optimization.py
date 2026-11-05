import numpy as np

from financial_ai_advisor_agents.schemas.portfolio import OptimizationResult, Portfolio


def project_bounded_simplex(
    values: np.ndarray,
    upper: np.ndarray,
    lower: np.ndarray | None = None,
) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    upper_bounds = np.asarray(upper, dtype=float)
    lower_bounds = np.zeros_like(vector) if lower is None else np.asarray(lower, dtype=float)
    if vector.ndim != 1 or upper_bounds.shape != vector.shape or lower_bounds.shape != vector.shape:
        raise ValueError("values and bounds must be one-dimensional arrays of equal shape")
    if np.any(lower_bounds < 0) or np.any(upper_bounds < lower_bounds):
        raise ValueError("bounds must satisfy 0 <= lower <= upper")
    if lower_bounds.sum() > 1 + 1e-12 or upper_bounds.sum() < 1 - 1e-12:
        raise ValueError("weight bounds cannot contain a fully invested portfolio")

    low = float(np.min(vector - upper_bounds))
    high = float(np.max(vector - lower_bounds))
    for _ in range(100):
        midpoint = (low + high) / 2.0
        projected = np.clip(vector - midpoint, lower_bounds, upper_bounds)
        if projected.sum() > 1.0:
            low = midpoint
        else:
            high = midpoint
    return np.clip(vector - (low + high) / 2.0, lower_bounds, upper_bounds)


def optimize_portfolio(
    portfolio: Portfolio,
    max_weight: float = 0.35,
    cash_min: float = 0.05,
    risk_aversion: float = 4.0,
    max_iterations: int = 2000,
    tolerance: float = 1e-11,
) -> OptimizationResult:
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight must be in (0, 1]")
    if not 0 <= cash_min <= max_weight:
        raise ValueError("cash_min must be between 0 and max_weight")
    if risk_aversion <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise ValueError("risk_aversion, max_iterations and tolerance must be positive")

    count = len(portfolio.holdings)
    if count * max_weight < 1 - 1e-12:
        raise ValueError("max_weight is too small for the number of holdings")
    cash_indexes = [
        index
        for index, holding in enumerate(portfolio.holdings)
        if holding.symbol == "CASH" or holding.sector.lower() in {"cash", "现金"} or "现金" in holding.name
    ]
    lower = np.zeros(count)
    effective_cash_min = cash_min if cash_indexes else 0.0
    for index in cash_indexes:
        lower[index] = effective_cash_min
    upper = np.full(count, max_weight)
    if lower.sum() > 1 + 1e-12:
        raise ValueError("cash minimums make the optimization constraints infeasible")

    market_values = np.array([h.quantity * h.current_price for h in portfolio.holdings], dtype=float)
    initial = project_bounded_simplex(market_values / market_values.sum(), upper, lower)
    expected = np.array([h.period_return for h in portfolio.holdings], dtype=float)
    history = np.array([h.return_history for h in portfolio.holdings], dtype=float)
    if history.shape[1] > 1:
        covariance = np.atleast_2d(np.cov(history, ddof=1)) * 12.0
    else:
        covariance = np.zeros((count, count))
    covariance = (covariance + covariance.T) / 2.0

    largest_eigenvalue = max(float(np.linalg.eigvalsh(covariance).max()), 0.0)
    step = 1.0 / (risk_aversion * largest_eigenvalue + 1e-6)
    weights = initial
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        gradient = expected - risk_aversion * covariance.dot(weights)
        updated = project_bounded_simplex(weights + step * gradient, upper, lower)
        iterations = iteration
        if np.linalg.norm(updated - weights, ord=1) < tolerance:
            weights = updated
            break
        weights = updated
    weights = project_bounded_simplex(weights, upper, lower)
    variance = max(float(weights.dot(covariance).dot(weights)), 0.0)
    cash_constraint = (
        f"cash_floor: each cash holding >= {effective_cash_min:.4f}"
        if cash_indexes
        else "cash_floor: 0.0000 (no cash holding)"
    )
    return OptimizationResult(
        weights={holding.symbol: float(weight) for holding, weight in zip(portfolio.holdings, weights)},
        expected_return=float(expected.dot(weights)),
        volatility=float(np.sqrt(variance)),
        constraints=[
            "long_only: every weight >= 0",
            "fully_invested: sum(weights) = 1",
            f"single_security_cap: every weight <= {max_weight:.4f}",
            cash_constraint,
        ],
        iterations=iterations,
        method="projected_gradient_mean_variance",
    )
