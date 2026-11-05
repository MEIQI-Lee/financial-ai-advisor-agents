from collections.abc import Sequence

from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.schemas.database import QueryRewriteResult
from financial_ai_advisor_agents.schemas.memory import Message


class QueryRewriteAgent:
    def __init__(self, llm: StructuredLLM, prompts: PromptLoader):
        self.llm = llm
        self.prompt = prompts.load("database/query_rewrite.md")

    def run(self, query: str, history: Sequence[Message] = ()) -> QueryRewriteResult:
        if not query.strip():
            raise ValueError("Query cannot be empty")
        payload = {"query": query, "history": [item.model_dump() for item in history]}
        return self.llm.generate_json("query_rewrite", self.prompt, payload, QueryRewriteResult)
