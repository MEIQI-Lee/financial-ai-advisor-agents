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
