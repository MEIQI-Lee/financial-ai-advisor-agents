from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.pipeline import Plan, TaskResult, TaskStatus, ValidationResult


class ValidationAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader):
        self.llm = llm
        self.prompt = prompts.load("main/validator.md")

    def run(self, query: str, plan: Plan, results: list[TaskResult]) -> ValidationResult:
        checks = ["必需任务状态检查", "结构化结果检查", "SQL证据检查"]
        by_id = {item.task_id: item for item in results}
        failed = []
        messages = []
        for task in plan.tasks:
            result = by_id.get(task.task_id)
            if not result:
                failed.append(task.task_id)
                messages.append(f"{task.task_id}: 没有执行结果")
                continue
            if task.required and result.status != TaskStatus.SUCCESS:
                failed.append(task.task_id)
                messages.append(f"{task.task_id}: {result.error or result.status.value}")
                continue
            if result.status == TaskStatus.SUCCESS and not result.data:
                failed.append(task.task_id)
                messages.append(f"{task.task_id}: 结构化结果为空")
                continue
            if "query_result" in result.data and not result.evidence:
                failed.append(task.task_id)
                messages.append(f"{task.task_id}: 缺少SQL证据")
        if failed:
            return ValidationResult(passed=False, failed_task_ids=failed, feedback="；".join(messages), checks=checks)
        llm_result = self.llm.generate_json("main_validator", self.prompt, {
            "query": query,
            "plan": plan.model_dump(mode="json"),
            "task_results": [item.model_dump(mode="json") for item in results],
            "hard_checks": {"passed": True, "checks": checks},
        }, ValidationResult)
        llm_result.checks = checks + llm_result.checks
        return llm_result
