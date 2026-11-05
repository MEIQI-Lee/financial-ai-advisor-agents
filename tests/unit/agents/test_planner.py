import pytest

from financial_ai_advisor_agents.schemas.memory import MemoryContext
from financial_ai_advisor_agents.schemas.pipeline import ExecutorType


def test_planner_routes_registered_metric_query(app):
    plan = app.planner.run("分析 RSI 超卖且均线多头排列的股票", MemoryContext(user_id="u"))
    assert plan.is_complex is True
    assert len(plan.tasks) == 1
    assert plan.tasks[0].executor_name == "database_qa"


def test_planner_does_not_invent_capability(app):
    plan = app.planner.run("帮我预测明天哪只股票涨停", MemoryContext(user_id="u"))
    assert plan.is_complex is False
    assert plan.tasks == []


@pytest.mark.parametrize(
    ("query", "executor_name", "executor_type"),
    [
        ("分析示例持仓并做组合优化", "portfolio_analysis", ExecutorType.WORKFLOW),
        ("查看我的KYC风险画像", "kyc", ExecutorType.WORKFLOW),
        ("什么是最大回撤", "rag", ExecutorType.WORKFLOW),
        ("计算股票的多维指标和综合评分", "financial_models", ExecutorType.FINANCIAL_MODEL),
    ],
)
def test_planner_routes_implemented_capabilities(app, query, executor_name, executor_type):
    plan = app.planner.run(query, MemoryContext(user_id="u"))
    assert len(plan.tasks) == 1
    assert plan.tasks[0].executor_name == executor_name
    assert plan.tasks[0].executor_type == executor_type
