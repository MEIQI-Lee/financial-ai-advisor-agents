from pathlib import Path

import numpy as np
import pytest

from financial_ai_advisor_agents.portfolio.optimization import optimize_portfolio, project_bounded_simplex
from financial_ai_advisor_agents.portfolio.risk import calculate_risk, cumulative_max_drawdown, historical_var_95
from financial_ai_advisor_agents.portfolio.service import PortfolioService


ROOT = Path(__file__).parents[3]
SAMPLE = ROOT / "data" / "mock" / "portfolio.json"


def test_sample_weights_returns_and_attribution_identities() -> None:
    service = PortfolioService(SAMPLE)
    portfolio = service.load_sample()
    analysis = service.analyze_sample()

    assert len(portfolio.holdings) >= 5
    assert len({len(h.return_history) for h in portfolio.holdings}) == 1
    assert all(len(h.return_history) >= 12 for h in portfolio.holdings)
    assert len(portfolio.benchmark_history) == len(portfolio.holdings[0].return_history)
    assert sum(row.weight for row in analysis.holdings) == pytest.approx(1.0)
    assert sum(sector.weight for sector in analysis.sectors) == pytest.approx(1.0)

    for source, row in zip(portfolio.holdings, analysis.holdings):
        expected_value = source.quantity * source.current_price
        assert row.market_value == pytest.approx(expected_value)
        assert row.weight == pytest.approx(expected_value / analysis.total_value)
        assert row.contribution == pytest.approx(row.weight * source.period_return)
        assert row.unrealized_pnl == pytest.approx(
            source.quantity * (source.current_price - source.cost_price)
        )

    assert analysis.total_return == pytest.approx(sum(item.contribution for item in analysis.attribution))
    assert analysis.active_return == pytest.approx(analysis.total_return - portfolio.benchmark_return)
    assert analysis.active_return == pytest.approx(sum(item.active_contribution for item in analysis.attribution))
    for item, source, row in zip(analysis.attribution, portfolio.holdings, analysis.holdings):
        assert item.active_contribution == pytest.approx(
            row.weight * (source.period_return - portfolio.benchmark_return)
        )
    assert analysis.total_pnl == pytest.approx(sum(row.unrealized_pnl for row in analysis.holdings))
    assert any("未经过 OCR" in assumption for assumption in analysis.assumptions)
    assert any("不是多期 Brinson" in assumption for assumption in analysis.assumptions)


def test_risk_metrics_match_definitions() -> None:
    returns = [0.10, -0.20, 0.05, -0.10]
    metrics = calculate_risk(returns, [0.6, 0.4], [0.7, 0.3])

    assert metrics.annualized_volatility == pytest.approx(np.std(returns, ddof=1) * np.sqrt(12))
    assert metrics.max_drawdown == pytest.approx(1 - (1.1 * 0.8 * 1.05 * 0.9) / 1.1)
    assert metrics.var_95 == pytest.approx(-np.percentile(returns, 5))
    assert metrics.hhi == pytest.approx(0.6**2 + 0.4**2)
    assert metrics.max_weight == pytest.approx(0.6)
    assert metrics.max_sector_weight == pytest.approx(0.7)
    assert 0 <= metrics.score <= 100
    assert cumulative_max_drawdown([0.1, 0.1]) == 0
    assert historical_var_95([0.01, 0.02]) == 0


def test_optimization_satisfies_all_constraints() -> None:
    portfolio = PortfolioService(SAMPLE).load_sample()
    result = optimize_portfolio(portfolio, max_weight=0.35, cash_min=0.08)

    assert sum(result.weights.values()) == pytest.approx(1.0, abs=1e-10)
    assert all(-1e-12 <= weight <= 0.35 + 1e-12 for weight in result.weights.values())
    assert result.weights["CASH"] >= 0.08 - 1e-12
    assert result.volatility >= 0
    assert result.iterations > 0
    assert result.method == "projected_gradient_mean_variance"
    assert len(result.constraints) == 4


def test_projection_and_infeasible_bounds() -> None:
    projected = project_bounded_simplex(
        np.array([0.9, 0.2, -0.1]),
        np.array([0.5, 0.5, 0.5]),
        np.array([0.0, 0.1, 0.0]),
    )
    assert projected.sum() == pytest.approx(1.0)
    assert np.all(projected >= np.array([0.0, 0.1, 0.0]) - 1e-12)
    assert np.all(projected <= 0.5 + 1e-12)

    portfolio = PortfolioService(SAMPLE).load_sample()
    with pytest.raises(ValueError, match="too small"):
        optimize_portfolio(portfolio, max_weight=0.1)
