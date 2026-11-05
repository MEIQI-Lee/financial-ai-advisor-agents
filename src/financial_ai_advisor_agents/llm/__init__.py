from financial_ai_advisor_agents.config import Settings
from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.llm.mock import MockLLM
from financial_ai_advisor_agents.llm.openai_compatible import OpenAICompatibleLLM


def create_llm(settings: Settings, registry: SchemaRegistry) -> StructuredLLM:
    if settings.mode == "mock":
        return MockLLM(registry)
    return OpenAICompatibleLLM(settings.openai_api_key, settings.openai_base_url, settings.openai_model)
