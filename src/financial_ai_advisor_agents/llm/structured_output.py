import json
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from financial_ai_advisor_agents.core.errors import StructuredOutputError

T = TypeVar("T")


def parse_structured(value: Any, schema: type[T]) -> T:
    try:
        if isinstance(value, str):
            value = json.loads(value)
        return TypeAdapter(schema).validate_python(value)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise StructuredOutputError(f"Structured output validation failed: {exc}") from exc


def is_object_schema(schema: type[Any]) -> bool:
    return isinstance(schema, type) and issubclass(schema, BaseModel)
