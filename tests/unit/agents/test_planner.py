from financial_ai_advisor_agents.schemas.memory import MemoryContext


def test_planner_routes_registered_metric_query(app):
    plan = app.planner.run("分析 RSI 超卖且均线多头排列的股票", MemoryContext(user_id="u"))
    assert plan.is_complex is True
    assert len(plan.tasks) == 1
    assert plan.tasks[0].executor_name == "database_qa"


def test_planner_does_not_invent_capability(app):
    plan = app.planner.run("帮我预测明天哪只股票涨停", MemoryContext(user_id="u"))
    assert plan.is_complex is False
    assert plan.tasks == []
