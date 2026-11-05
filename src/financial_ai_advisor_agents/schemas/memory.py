from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str


class MemoryContext(BaseModel):
    user_id: str
    profile: dict[str, Any] = Field(default_factory=dict)
    history: list[Message] = Field(default_factory=list)
