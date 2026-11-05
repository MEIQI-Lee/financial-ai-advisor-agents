from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self


class Holding(BaseModel):
    symbol: str = Field(min_length=1)
    name: str
    sector: str = Field(min_length=1)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    current_price: float = Field(gt=0, allow_inf_nan=False)
    cost_price: float = Field(ge=0, allow_inf_nan=False)
    period_return: float = Field(ge=-1, allow_inf_nan=False)
    return_history: list[float] = Field(min_length=1)

    @field_validator("symbol", "name", "sector")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()

    @field_validator("return_history")
    @classmethod
    def validate_history(cls, values: list[float]) -> list[float]:
        if any(not isinstance(value, (int, float)) for value in values):
            raise ValueError("return_history must contain numbers")
        if any(value < -1 or value != value or abs(value) == float("inf") for value in values):
            raise ValueError("returns must be finite and no less than -1")
        return [float(value) for value in values]


class Portfolio(BaseModel):
    holdings: list[Holding] = Field(min_length=1)
    benchmark_return: float = Field(ge=-1, allow_inf_nan=False)
    benchmark_history: list[float] = Field(min_length=1)

    @field_validator("benchmark_history")
    @classmethod
    def validate_benchmark_history(cls, values: list[float]) -> list[float]:
        if any(value < -1 or value != value or abs(value) == float("inf") for value in values):
            raise ValueError("benchmark returns must be finite and no less than -1")
        return [float(value) for value in values]

    @model_validator(mode="after")
    def validate_series_and_symbols(self) -> Self:
        lengths = {len(holding.return_history) for holding in self.holdings}
        lengths.add(len(self.benchmark_history))
        if len(lengths) != 1:
            raise ValueError("all return histories and benchmark_history must have equal length")
        symbols = [holding.symbol for holding in self.holdings]
        if len(set(symbols)) != len(symbols):
            raise ValueError("holding symbols must be unique")
        return self


class HoldingAnalysis(BaseModel):
    symbol: str
    name: str
    sector: str
    weight: float = Field(ge=0, le=1)
    period_return: float
    contribution: float
    market_value: float = Field(ge=0)
    unrealized_pnl: float
    signal: str


class SectorAllocation(BaseModel):
    sector: str
    weight: float = Field(ge=0, le=1)


class RiskMetrics(BaseModel):
    score: float = Field(ge=0, le=100)
    level: str
    annualized_volatility: float = Field(ge=0)
    max_drawdown: float = Field(ge=0)
    var_95: float = Field(ge=0)
    hhi: float = Field(ge=0, le=1)
    max_weight: float = Field(ge=0, le=1)
    max_sector_weight: float = Field(ge=0, le=1)


class AttributionItem(BaseModel):
    symbol: str
    contribution: float
    active_contribution: float


class OptimizationResult(BaseModel):
    weights: dict[str, float]
    expected_return: float
    volatility: float = Field(ge=0)
    constraints: list[str]
    iterations: int = Field(ge=0)
    method: str


class PortfolioAnalysis(BaseModel):
    portfolio: Portfolio
    holdings: list[HoldingAnalysis]
    sectors: list[SectorAllocation]
    risk: RiskMetrics
    attribution: list[AttributionItem]
    total_return: float
    benchmark_return: float
    active_return: float
    total_value: float = Field(ge=0)
    total_pnl: float
    diagnoses: list[str]
    optimization: OptimizationResult
    assumptions: list[str]
