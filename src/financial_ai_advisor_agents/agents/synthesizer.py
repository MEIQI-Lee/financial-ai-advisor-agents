from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.pipeline import FinalResponse, TaskResult


class SynthesisAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader):
        self.llm = llm
        self.prompt = prompts.load("main/synthesizer.md")

    def run(self, query: str, results: list[TaskResult]) -> FinalResponse:
        payload = {"query": query, "task_results": [item.model_dump(mode="json") for item in results]}
        return self.llm.generate_json("main_synthesizer", self.prompt, payload, FinalResponse)
