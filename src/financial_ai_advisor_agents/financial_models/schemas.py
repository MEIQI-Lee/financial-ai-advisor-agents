from pydantic import BaseModel, Field, field_validator


class Security(BaseModel):
    symbol: str
    name: str
    sector: str
    trade_date: str
    close: float = Field(gt=0, allow_inf_nan=False)
    rsi_14: float = Field(ge=0, le=100, allow_inf_nan=False)
    ma_trend: str
    macd_signal: str
    boll_upper: float = Field(gt=0, allow_inf_nan=False)
    boll_middle: float = Field(gt=0, allow_inf_nan=False)
    boll_lower: float = Field(gt=0, allow_inf_nan=False)
    debt_ratio: float = Field(ge=0, allow_inf_nan=False)
    gross_margin: float = Field(allow_inf_nan=False)
    eps: float = Field(allow_inf_nan=False)
    dividend_yield: float = Field(ge=0, allow_inf_nan=False)
    pe_ratio: float = Field(allow_inf_nan=False)
    pb_ratio: float = Field(allow_inf_nan=False)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", "sector", "trade_date")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("ma_trend", "macd_signal")
    @classmethod
    def normalize_signal(cls, value: str) -> str:
        return value.strip().upper()


class SecurityScore(BaseModel):
    symbol: str
    name: str
    sector: str
    total_score: float = Field(ge=0, le=100)
    valuation_score: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    technical_score: float = Field(ge=0, le=100)
    dividend_score: float = Field(ge=0, le=100)
    components: dict[str, float]


class FundamentalReport(BaseModel):
    symbol: str
    name: str
    sector: str
    trade_date: str
    close: float
    pe_ratio: float
    pb_ratio: float
    debt_ratio: float
    gross_margin: float
    eps: float
    dividend_yield: float
    rsi_14: float
    ma_trend: str
    macd_signal: str
    score: SecurityScore
    risk_flags: list[str]
    summary: str
    assumptions: list[str]
