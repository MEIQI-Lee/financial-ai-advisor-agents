from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.database import MetricEntity


class MetricEntityExtractionAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader):
        self.llm = llm
        self.prompt = prompts.load("database/metric_entity_extraction.md")

    def run(self, query: str) -> list[MetricEntity]:
        if not query.strip():
            raise ValueError("Query cannot be empty")
        return self.llm.generate_json("metric_extraction", self.prompt, {"query": query}, list[MetricEntity])
