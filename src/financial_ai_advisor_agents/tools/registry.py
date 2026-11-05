from dataclasses import dataclass
from typing import Any, Callable

from financial_ai_advisor_agents.core.errors import CapabilityError
from financial_ai_advisor_agents.schemas.pipeline import ExecutorType, TaskSpec

CapabilityHandler = Callable[[TaskSpec, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Capability:
    name: str
    executor_type: ExecutorType
    description: str
    handler: CapabilityHandler


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    def register(self, name: str, executor_type: ExecutorType, description: str, handler: CapabilityHandler) -> None:
        if name in self._capabilities:
            raise CapabilityError(f"Capability already registered: {name}")
        self._capabilities[name] = Capability(name, executor_type, description, handler)

    def execute(self, task: TaskSpec, context: dict[str, Any]) -> dict[str, Any]:
        capability = self._capabilities.get(task.executor_name)
        if not capability:
            raise CapabilityError(f"Unknown capability: {task.executor_name}")
        if capability.executor_type != task.executor_type:
            raise CapabilityError(f"Executor type mismatch for {task.executor_name}")
        return capability.handler(task, context)

    def descriptions(self) -> dict[str, dict[str, str]]:
        return {
            name: {"type": item.executor_type.value, "description": item.description}
            for name, item in self._capabilities.items()
        }

    def validate_plan(self, tasks: list[TaskSpec]) -> None:
        task_ids = {task.task_id for task in tasks}
        if len(task_ids) != len(tasks):
            raise CapabilityError("Task IDs must be unique")
        for task in tasks:
            capability = self._capabilities.get(task.executor_name)
            if not capability or capability.executor_type != task.executor_type:
                raise CapabilityError(f"Planner selected an unavailable capability: {task.executor_name}")
            if any(dependency not in task_ids for dependency in task.dependencies):
                raise CapabilityError(f"Task {task.task_id} has an unknown dependency")
