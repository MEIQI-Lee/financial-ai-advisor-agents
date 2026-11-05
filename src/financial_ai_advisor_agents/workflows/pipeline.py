from uuid import uuid4

from financial_ai_advisor_agents.memory.store import MemoryStore
from financial_ai_advisor_agents.schemas.pipeline import FinalResponse, PipelineResult, TaskResult, ValidationResult


class FourStagePipeline:
    def __init__(self, planner, executor, validator, synthesizer, memory: MemoryStore, max_replans: int = 2, history_limit: int = 6):
        self.planner = planner
        self.executor = executor
        self.validator = validator
        self.synthesizer = synthesizer
        self.memory = memory
        self.max_replans = max_replans
        self.history_limit = history_limit

    def run(self, query: str, user_id: str = "demo-user") -> PipelineResult:
        if not query.strip():
            raise ValueError("Query cannot be empty")
        run_id = uuid4().hex[:12]
        memory = self.memory.context(user_id, self.history_limit)
        feedback = ""
        previous_results: list[TaskResult] = []
        plan = None
        validation = ValidationResult(passed=False, feedback="Pipeline has not run")
        results: list[TaskResult] = []
        for iteration in range(self.max_replans + 1):
            plan = self.planner.run(query, memory, feedback, previous_results, iteration)
            results = self.executor.run(plan, query, memory)
            validation = self.validator.run(query, plan, results)
            if validation.passed:
                final = self.synthesizer.run(query, results)
                return self._finish(run_id, user_id, query, final, plan, results, validation, iteration)
            previous_results = results
            feedback = validation.feedback or "验证未通过，请修正任务"
        final = FinalResponse(
            status="failed",
            answer=f"经过 {self.max_replans} 次重规划仍未通过验证：{validation.feedback}",
            warnings=["未将失败任务交给融合代理生成结论"],
        )
        return self._finish(run_id, user_id, query, final, plan, results, validation, self.max_replans)

    def _finish(self, run_id, user_id, query, final, plan, results, validation, replan_count) -> PipelineResult:
        result = PipelineResult(
            run_id=run_id,
            query=query,
            final=final,
            plan=plan,
            task_results=results,
            validation=validation,
            replan_count=replan_count,
        )
        self.memory.append_message(user_id, "user", query)
        self.memory.append_message(user_id, "assistant", final.answer)
        return result
