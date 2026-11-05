from pathlib import Path


def test_database_workflow_returns_rows_and_chart(app):
    result = app.database_workflow.run("筛选 RSI 超卖且均线多头排列的股票，并生成图表")
    assert result.query_result.row_count == 3
    assert [row["symbol"] for row in result.query_result.rows] == ["DEMO01", "DEMO02", "DEMO03"]
    assert result.postprocess.chart_path
    assert Path(result.postprocess.chart_path).exists()


def test_database_workflow_treats_empty_rows_as_valid_result(app):
    result = app.database_workflow.run("筛选 RSI 超买的股票")
    assert result.query_result.row_count == 0
    assert result.query_result.rows == []
    assert result.postprocess.chart_path == ""


def test_database_workflow_supports_fundamental_filter(app):
    result = app.database_workflow.run("筛选资产负债率低于40%的股票")
    assert result.query_result.row_count == 2
    assert {row["symbol"] for row in result.query_result.rows} == {"DEMO03", "DEMO04"}
