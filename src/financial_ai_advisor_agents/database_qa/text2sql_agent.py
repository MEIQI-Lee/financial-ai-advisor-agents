from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.database import SemanticAnalysisResult, Text2SQLResult


class Text2SQLAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader, max_rows: int = 50):
        self.llm = llm
        self.prompt = prompts.load("database/text2sql.md")
        self.max_rows = max_rows

    def run(self, semantic: SemanticAnalysisResult, feedback: str = "") -> Text2SQLResult:
        if semantic.unaligned_entities:
            raise ValueError(f"Unaligned entities: {', '.join(semantic.unaligned_entities)}")
        if not semantic.aligned_entities:
            raise ValueError("No registered metric entities were extracted")
        payload = {"semantic": semantic.model_dump(), "max_rows": self.max_rows, "feedback": feedback}
        return self.llm.generate_json("text2sql", self.prompt, payload, Text2SQLResult)
