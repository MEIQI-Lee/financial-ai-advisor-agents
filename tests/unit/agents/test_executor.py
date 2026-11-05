from financial_ai_advisor_agents.agents.executor import ExecutionAgent
from financial_ai_advisor_agents.schemas.memory import MemoryContext
from financial_ai_advisor_agents.schemas.pipeline import ExecutorType, Plan, TaskSpec, TaskStatus
from financial_ai_advisor_agents.tools.registry import CapabilityRegistry


def test_executor_respects_dependencies():
    calls = []
    registry = CapabilityRegistry()
    registry.register("first", ExecutorType.TOOL, "first", lambda task, context: calls.append("first") or {"value": 1})
    registry.register("second", ExecutorType.TOOL, "second", lambda task, context: calls.append("second") or {"value": 2})
    second = TaskSpec(task_id="second", objective="second", executor_type=ExecutorType.TOOL, executor_name="second", dependencies=["first"])
    first = TaskSpec(task_id="first", objective="first", executor_type=ExecutorType.TOOL, executor_name="first")
    results = ExecutionAgent(registry).run(Plan(is_complex=True, tasks=[second, first]), "q", MemoryContext(user_id="u"))
    assert calls == ["first", "second"]
    assert [item.task_id for item in results] == ["first", "second"]


def test_executor_skips_task_after_failed_dependency():
    registry = CapabilityRegistry()
    def fail(task, context):
        raise RuntimeError("boom")
    registry.register("first", ExecutorType.TOOL, "first", fail)
    registry.register("second", ExecutorType.TOOL, "second", lambda task, context: {"value": 2})
    first = TaskSpec(task_id="first", objective="first", executor_type=ExecutorType.TOOL, executor_name="first")
    second = TaskSpec(task_id="second", objective="second", executor_type=ExecutorType.TOOL, executor_name="second", dependencies=["first"])
    results = ExecutionAgent(registry).run(Plan(is_complex=True, tasks=[first, second]), "q", MemoryContext(user_id="u"))
    assert results[0].status == TaskStatus.FAILED
    assert results[1].status == TaskStatus.SKIPPED
