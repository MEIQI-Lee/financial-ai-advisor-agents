import json
from typing import Any, TypeVar

from openai import OpenAI

from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.llm.structured_output import is_object_schema, parse_structured

T = TypeVar("T")


class OpenAICompatibleLLM(StructuredLLM):
    def __init__(self, api_key: str, base_url: str, model: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when APP_MODE=openai")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def generate_json(self, operation: str, prompt: str, payload: dict[str, Any], schema: type[T]) -> T:
        request: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
        }
        if is_object_schema(schema):
            request["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(**request)
        content = response.choices[0].message.content
        if not content:
            raise ValueError(f"LLM returned empty content for {operation}")
        return parse_structured(content, schema)
