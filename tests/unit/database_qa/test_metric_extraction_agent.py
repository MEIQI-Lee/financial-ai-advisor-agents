from financial_ai_advisor_agents.schemas.database import MetricEntity


def test_extracts_only_listed_bollinger_entity(app):
    result = app.database_workflow.metric_extraction.run("筛选出布林线下轨突破的股票；分析突破后的股价走势")
    assert result == [MetricEntity(entity_name="布林线下轨突破", datetime="", entity_type="股票")]


def test_extracts_multiple_entities_without_inventing_fields(app):
    result = app.database_workflow.metric_extraction.run("筛选 RSI 超卖、MACD金叉且 ROE 较高的股票")
    assert {item.entity_name for item in result} == {"RSI超卖", "MACD金叉"}
    assert all(item.datetime == "" for item in result)


def test_semantic_analysis_reads_fundamental_threshold(app):
    entities = app.database_workflow.metric_extraction.run("资产负债率低于40%")
    semantic = app.database_workflow.semantic_analysis.run("资产负债率低于40%", entities)
    aligned = semantic.aligned_entities[0]
    assert aligned.column == "debt_ratio"
    assert aligned.operator == "<"
    assert aligned.value == 40.0
