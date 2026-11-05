from pathlib import Path

import pytest

from financial_ai_advisor_agents.financial_models import FinancialModelSuite, SecurityUniverse


ROOT = Path(__file__).parents[3]
CSV_PATH = ROOT / "data" / "mock" / "securities.csv"


def test_security_universe_and_multidimensional_scores() -> None:
    universe = SecurityUniverse(CSV_PATH)
    suite = FinancialModelSuite(CSV_PATH)
    scores = suite.score_securities()
    by_symbol = {score.symbol: score for score in scores}

    assert len(universe.load()) == 6
    assert len(scores) == 6
    assert [score.total_score for score in scores] == sorted(
        [score.total_score for score in scores], reverse=True
    )
    for score in scores:
        assert 0 <= score.total_score <= 100
        assert 0 <= score.valuation_score <= 100
        assert 0 <= score.quality_score <= 100
        assert 0 <= score.technical_score <= 100
        assert 0 <= score.dividend_score <= 100
        assert score.total_score == pytest.approx(
            0.30 * score.valuation_score
            + 0.30 * score.quality_score
            + 0.25 * score.technical_score
            + 0.15 * score.dividend_score,
            abs=2e-6,
        )

    assert by_symbol["DEMO05"].valuation_score == pytest.approx(100)
    assert by_symbol["DEMO05"].dividend_score == pytest.approx(100)
    assert by_symbol["DEMO04"].valuation_score == pytest.approx(0)
    assert by_symbol["DEMO04"].dividend_score == pytest.approx(0)
    assert by_symbol["DEMO06"].components["ma_trend"] == 0
    assert by_symbol["DEMO06"].components["macd"] == 0
    assert "min-max" in suite.normalization_rules["cross_section"]


def test_fundamental_report_is_csv_driven_and_flags_risks() -> None:
    suite = FinancialModelSuite(CSV_PATH)
    report = suite.fundamental("demo05")

    assert report.symbol == "DEMO05"
    assert report.close == pytest.approx(9.86)
    assert report.debt_ratio == pytest.approx(88.4)
    assert report.dividend_yield == pytest.approx(4.35)
    assert report.score.total_score >= 0
    assert any("负债率" in flag for flag in report.risk_flags)
    assert "9.86" not in report.summary
    assert any("虚构 CSV" in assumption for assumption in report.assumptions)

    weak_report = suite.fundamental("DEMO06")
    assert any("BEARISH" in flag for flag in weak_report.risk_flags)
    assert any("DEAD_CROSS" in flag for flag in weak_report.risk_flags)


def test_unknown_symbol_raises_value_error() -> None:
    suite = FinancialModelSuite(CSV_PATH)
    with pytest.raises(ValueError, match="unknown security symbol"):
        suite.fundamental("NOT_THERE")
    with pytest.raises(ValueError, match="unknown security symbol"):
        SecurityUniverse(CSV_PATH).get("NOT_THERE")
