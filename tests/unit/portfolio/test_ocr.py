import builtins
from pathlib import Path

import pytest

from financial_ai_advisor_agents.portfolio.ocr import PaddleOCREngine, parse_ocr_line, parse_ocr_lines
from financial_ai_advisor_agents.portfolio.service import PortfolioService


ROOT = Path(__file__).parents[3]
SAMPLE = ROOT / "data" / "mock" / "portfolio.json"


class FakeEngine:
    def extract_text(self, content: bytes, filename: str) -> list[str]:
        assert content == b"fake image"
        assert filename == "positions.png"
        return [
            "DEMO01 示例科技 科技 100 18.42 16.00 12%",
            "DEMO02 示例制造 制造 80 26.75 24.50 8%",
            "CASH 示例现金 现金 1 2000 2000 0.3%",
        ]


def test_parse_plain_and_keyed_ocr_rows() -> None:
    plain = parse_ocr_line("DEMO09 示例证券 科技 100 10.5 8.0 25%")
    keyed = parse_ocr_line(
        "代码:DEMO10 名称:示例 keyed 行业:制造 数量:20 现价:12 成本:10 收益率:20%"
    )

    assert plain.symbol == "DEMO09"
    assert plain.quantity == 100
    assert plain.current_price == 10.5
    assert plain.cost_price == 8
    assert plain.period_return == pytest.approx(0.25)
    assert len(plain.return_history) == 12
    assert keyed.name == "示例"
    assert keyed.sector == "制造"
    assert keyed.period_return == pytest.approx(0.2)

    inferred = parse_ocr_line("DEMO11 示例推断 消费 10 11 10")
    assert inferred.period_return == pytest.approx(0.1)


def test_ocr_rejects_incomplete_or_empty_rows() -> None:
    with pytest.raises(ValueError, match="requires quantity"):
        parse_ocr_line("DEMO09 示例证券 科技 10.5 8.0")
    with pytest.raises(ValueError, match="did not produce"):
        parse_ocr_lines(["证券代码 名称 行业 数量 现价 成本"])


def test_analyze_image_uses_injected_engine_and_discloses_placeholders() -> None:
    analysis = PortfolioService(SAMPLE, ocr_engine=FakeEngine()).analyze_image(b"fake image", "positions.png")

    assert [holding.symbol for holding in analysis.portfolio.holdings] == ["DEMO01", "DEMO02", "CASH"]
    assert analysis.benchmark_return == 0
    assert sum(row.weight for row in analysis.holdings) == pytest.approx(1)
    assert any("需人工核对" in assumption for assumption in analysis.assumptions)
    assert any("零收益仅用于占位" in assumption for assumption in analysis.assumptions)


def test_analyze_image_reports_missing_paddleocr(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def block_paddle(name: str, *args: object, **kwargs: object) -> object:
        if name == "paddleocr":
            raise ImportError("blocked for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_paddle)
    with pytest.raises(RuntimeError, match="PaddleOCR is not installed"):
        PortfolioService(SAMPLE).analyze_image(b"image", "positions.png")
    with pytest.raises(RuntimeError, match="optional 'paddleocr'"):
        PaddleOCREngine()
