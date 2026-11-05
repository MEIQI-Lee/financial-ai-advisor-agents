from typing import Any

from pydantic import BaseModel, Field


class KYCOption(BaseModel):
    value: str
    label: str
    score: int


class KYCQuestion(BaseModel):
    id: str
    title: str
    options: list[KYCOption]


class MarketEnvironment(BaseModel):
    economic_cycle: str = ""
    market_interest_rate: str = ""
    policies_and_regulations: str = ""


class KYCState(BaseModel):
    user_id: str
    step: int = 0
    answers: dict[str, str] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    completed: bool = False
    risk_level: str | None = None
    risk_score: int | None = None
    allocation: dict[str, int] = Field(default_factory=dict)
    allocation_explanation: str = ""
    market_environment: MarketEnvironment = Field(default_factory=MarketEnvironment)
    question: KYCQuestion | None = None
