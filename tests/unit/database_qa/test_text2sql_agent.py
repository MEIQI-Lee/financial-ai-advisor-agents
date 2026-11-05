import pytest

from financial_ai_advisor_agents.schemas.database import SemanticAnalysisResult


def test_text2sql_builds_select_from_aligned_entities(app):
    query = "RSI 超卖且均线多头排列"
    entities = app.database_workflow.metric_extraction.run(query)
    semantic = app.database_workflow.semantic_analysis.run(query, entities)
    result = app.database_workflow.text2sql.run(semantic)
    assert "rsi_14 < 30" in result.sql
    assert "ma_trend = 'BULLISH'" in result.sql
    assert result.sql.endswith("LIMIT 50")
    assert result.tables == ["mock_securities"]


def test_text2sql_rejects_unaligned_entities(app):
    semantic = SemanticAnalysisResult(
        rewritten_query="未知指标",
        aligned_entities=[],
        schema_text="",
        unaligned_entities=["未知指标"],
    )
    with pytest.raises(ValueError, match="Unaligned"):
        app.database_workflow.text2sql.run(semantic)
