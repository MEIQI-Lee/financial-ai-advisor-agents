from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecutorType(str, Enum):
    WORKFLOW = "workflow"
    TOOL = "tool"
    FINANCIAL_MODEL = "financial_model"


class TaskSpec(BaseModel):
    task_id: str
    objective: str
    executor_type: ExecutorType = ExecutorType.WORKFLOW
    executor_name: str
    input_bindings: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    required: bool = True


class Plan(BaseModel):
    is_complex: bool
    reasoning_summary: str = ""
    tasks: list[TaskSpec] = Field(default_factory=list)
    iteration: int = 0


class TaskStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Evidence(BaseModel):
    kind: str
    reference: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    error: str = ""


class ValidationResult(BaseModel):
    passed: bool
    failed_task_ids: list[str] = Field(default_factory=list)
    feedback: str = ""
    checks: list[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    status: str
    answer: str
    assumptions: list[str] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    run_id: str
    query: str
    final: FinalResponse
    plan: Plan
    task_results: list[TaskResult] = Field(default_factory=list)
    validation: ValidationResult
    replan_count: int = 0
