from pathlib import Path

from financial_ai_advisor_agents.schemas.database import QueryResult, Text2SQLResult
from financial_ai_advisor_agents.schemas.memory import Message


def test_query_rewrite_agent_runs_independently(app):
    history = [Message(role="user", content="之前的筛选"), Message(role="assistant", content="之前的结果")]
    result = app.database_workflow.query_rewrite.run("RSI 超卖", history)
    assert result.original_query == "RSI 超卖"
    assert result.rewritten_query == "RSI 超卖"


def test_dialogue_planning_agent_runs_independently(app):
    result = app.database_workflow.dialogue_planner.run("对比 RSI 超卖股票并生成图表")
    assert result.requires_chart is True
    assert result.steps == ["指标实体抽取", "实体对齐与Schema拼接", "Text2SQL", "SQL执行", "数据后处理"]


def test_sql_execution_agent_runs_independently(app):
    statement = Text2SQLResult(sql="SELECT symbol, rsi_14 FROM mock_securities WHERE rsi_14 < 30 ORDER BY rsi_14 ASC LIMIT 50")
    result = app.database_workflow.sql_execution.run(statement)
    assert result.row_count == 3
    assert result.columns == ["symbol", "rsi_14"]


def test_postprocessing_agent_runs_independently(app):
    query_result = QueryResult(
        columns=["symbol", "rsi_14"],
        rows=[{"symbol": "DEMO01", "rsi_14": 24.8}],
        row_count=1,
        sql="SELECT symbol, rsi_14 FROM mock_securities LIMIT 1",
    )
    result = app.database_workflow.postprocessing.run(query_result, ["rsi_14"])
    assert result.summary["numeric_averages"]["rsi_14"] == 24.8
    assert Path(result.chart_path).exists()
