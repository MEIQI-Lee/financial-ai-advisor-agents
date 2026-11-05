from financial_ai_advisor_agents.agents.executor import ExecutionAgent
from financial_ai_advisor_agents.agents.planner import PlanningAgent
from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.memory.store import MemoryStore
from financial_ai_advisor_agents.schemas.pipeline import ExecutorType
from financial_ai_advisor_agents.tools.registry import CapabilityRegistry
from financial_ai_advisor_agents.workflows.pipeline import FourStagePipeline


def test_pipeline_end_to_end_and_memory(app):
    result = app.pipeline.run("筛选 RSI 超卖且均线多头排列的股票", "integration-user")
    assert result.final.status == "success"
    assert result.validation.passed is True
    assert result.task_results[0].data["query_result"]["row_count"] == 3
    history = app.pipeline.memory.context("integration-user").history
    assert [item.role for item in history] == ["user", "assistant"]


def test_pipeline_returns_unsupported_without_fabricating_answer(app):
    result = app.pipeline.run("预测明天涨停的股票", "integration-user")
    assert result.final.status == "unsupported"
    assert result.plan.tasks == []
    assert result.task_results == []


def _replan_pipeline(app, handler, max_replans=1):
    registry = CapabilityRegistry()
    registry.register("database_qa", ExecutorType.WORKFLOW, "test database", handler)
    prompts = PromptLoader(app.settings.prompt_dir)
    planner = PlanningAgent(app.llm, prompts, registry)
    return FourStagePipeline(
        planner,
        ExecutionAgent(registry),
        app.validator,
        app.synthesizer,
        MemoryStore(app.settings.memory_path),
        max_replans=max_replans,
    )


def test_pipeline_replans_after_execution_failure(app):
    calls = 0
    def flaky(task, context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary SQL failure")
        return app.database_workflow.run(context["query"]).model_dump(mode="json")
    result = _replan_pipeline(app, flaky).run("RSI 超卖", "retry-user")
    assert calls == 2
    assert result.replan_count == 1
    assert result.final.status == "success"


def test_pipeline_stops_after_retry_limit(app):
    def always_fails(task, context):
        raise RuntimeError("persistent failure")
    result = _replan_pipeline(app, always_fails).run("RSI 超卖", "retry-user")
    assert result.replan_count == 1
    assert result.final.status == "failed"
    assert "未将失败任务" in result.final.warnings[0]


def test_pipeline_runs_portfolio_analysis(app):
    result = app.pipeline.run("分析示例持仓并做组合优化", "portfolio-user")
    assert result.final.status == "success"
    assert result.plan.tasks[0].executor_name == "portfolio_analysis"
    assert result.task_results[0].data["optimization"]["weights"]
    assert result.task_results[0].evidence[0].kind == "portfolio"
    assert "虚构示例持仓" in result.final.answer


def test_pipeline_reports_kyc_progress_without_allocation(app):
    result = app.pipeline.run("查看我的KYC风险画像", "kyc-user")
    assert result.final.status == "success"
    assert "已完成 0/5 题" in result.final.answer
    assert result.task_results[0].data["allocation"] == {}


def test_pipeline_runs_rag_with_citations(app):
    result = app.pipeline.run("什么是最大回撤", "rag-user")
    assert result.final.status == "success"
    assert result.final.sources
    assert result.final.sources[0].kind == "knowledge"
    assert "[1]" in result.final.answer


def test_pipeline_runs_financial_model_scores(app):
    result = app.pipeline.run("计算股票的多维指标和综合评分", "model-user")
    assert result.final.status == "success"
    assert result.plan.tasks[0].executor_type == ExecutorType.FINANCIAL_MODEL
    assert len(result.task_results[0].data["scores"]) == 6
    assert "未来收益预测" in result.final.warnings[0]
