from abc import ABC, abstractmethod
from typing import Any, TypeVar

T = TypeVar("T")


class StructuredLLM(ABC):
    @abstractmethod
    def generate_json(self, operation: str, prompt: str, payload: dict[str, Any], schema: type[T]) -> T:
        raise NotImplementedError
