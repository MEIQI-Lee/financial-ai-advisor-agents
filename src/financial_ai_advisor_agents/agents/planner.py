from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.memory import MemoryContext
from financial_ai_advisor_agents.schemas.pipeline import Plan, TaskResult
from financial_ai_advisor_agents.tools.registry import CapabilityRegistry


class PlanningAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader, capabilities: CapabilityRegistry):
        self.llm = llm
        self.prompt = prompts.load("main/planner.md")
        self.capabilities = capabilities

    def run(self, query: str, memory: MemoryContext, feedback: str = "", previous_results: list[TaskResult] | None = None, iteration: int = 0) -> Plan:
        payload = {
            "query": query,
            "profile": memory.profile,
            "history": [item.model_dump() for item in memory.history],
            "capabilities": self.capabilities.descriptions(),
            "feedback": feedback,
            "previous_results": [item.model_dump(mode="json") for item in previous_results or []],
            "iteration": iteration,
        }
        plan = self.llm.generate_json("main_planner", self.prompt, payload, Plan)
        plan.iteration = iteration
        self.capabilities.validate_plan(plan.tasks)
        return plan
