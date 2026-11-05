from typing import Any

from financial_ai_advisor_agents.schemas.memory import MemoryContext
from financial_ai_advisor_agents.schemas.pipeline import Evidence, Plan, TaskResult, TaskSpec, TaskStatus
from financial_ai_advisor_agents.tools.registry import CapabilityRegistry


class ExecutionAgent:
    def __init__(self, capabilities: CapabilityRegistry):
        self.capabilities = capabilities

    def run(self, plan: Plan, query: str, memory: MemoryContext) -> list[TaskResult]:
        pending = {task.task_id: task for task in plan.tasks}
        completed: dict[str, TaskResult] = {}
        ordered_results: list[TaskResult] = []
        while pending:
            progressed = False
            for task_id, task in list(pending.items()):
                if any(dependency not in completed for dependency in task.dependencies):
                    continue
                progressed = True
                dependency_results = [completed[item] for item in task.dependencies]
                if any(item.status != TaskStatus.SUCCESS for item in dependency_results):
                    result = TaskResult(task_id=task_id, status=TaskStatus.SKIPPED, error="A dependency did not succeed")
                else:
                    result = self._execute(task, query, memory, dependency_results)
                completed[task_id] = result
                ordered_results.append(result)
                del pending[task_id]
            if not progressed:
                for task_id, task in pending.items():
                    result = TaskResult(task_id=task_id, status=TaskStatus.FAILED, error="Cyclic task dependencies detected")
                    completed[task_id] = result
                    ordered_results.append(result)
                break
        return ordered_results

    def _execute(self, task: TaskSpec, query: str, memory: MemoryContext, dependencies: list[TaskResult]) -> TaskResult:
        try:
            context: dict[str, Any] = {
                "query": query,
                "memory": memory,
                "dependencies": dependencies,
            }
            data = self.capabilities.execute(task, context)
            return TaskResult(task_id=task.task_id, status=TaskStatus.SUCCESS, data=data, evidence=self._evidence(data))
        except Exception as exc:
            return TaskResult(task_id=task.task_id, status=TaskStatus.FAILED, error=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _evidence(data: dict[str, Any]) -> list[Evidence]:
        evidence = []
        query_result = data.get("query_result")
        if query_result:
            evidence.append(Evidence(
                kind="sql",
                reference="mock_securities",
                detail={"sql": query_result["sql"], "row_count": query_result["row_count"]},
            ))
        chart_path = data.get("postprocess", {}).get("chart_path", "")
        if chart_path:
            evidence.append(Evidence(kind="chart", reference=chart_path))
        return evidence
