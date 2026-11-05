from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.database import DialoguePlan


class DialoguePlanningAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader):
        self.llm = llm
        self.prompt = prompts.load("database/dialogue_planner.md")

    def run(self, query: str) -> DialoguePlan:
        return self.llm.generate_json("dialogue_planner", self.prompt, {"query": query}, DialoguePlan)
