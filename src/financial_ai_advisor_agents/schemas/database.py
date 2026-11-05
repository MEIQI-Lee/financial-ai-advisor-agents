from typing import Any

from pydantic import BaseModel, Field


class MetricEntity(BaseModel):
    entity_name: str
    datetime: str = ""
    entity_type: str = "股票"


class QueryRewriteResult(BaseModel):
    original_query: str
    rewritten_query: str
    reasoning_summary: str = ""


class DialoguePlan(BaseModel):
    steps: list[str] = Field(default_factory=list)
    requires_chart: bool = False


class AlignedEntity(BaseModel):
    entity_name: str
    canonical_name: str
    table: str
    column: str
    operator: str = ""
    value: Any = ""
    datetime: str = ""
    entity_type: str = "股票"


class SemanticAnalysisResult(BaseModel):
    rewritten_query: str
    aligned_entities: list[AlignedEntity] = Field(default_factory=list)
    schema_text: str
    unaligned_entities: list[str] = Field(default_factory=list)


class Text2SQLResult(BaseModel):
    sql: str
    rationale: str = ""
    tables: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    sql: str
    truncated: bool = False


class PostProcessResult(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    chart_path: str = ""


class DatabaseQAResult(BaseModel):
    original_query: str
    rewritten_query: str
    dialogue_steps: list[str] = Field(default_factory=list)
    entities: list[MetricEntity] = Field(default_factory=list)
    semantic: SemanticAnalysisResult
    text2sql: Text2SQLResult
    query_result: QueryResult
    postprocess: PostProcessResult
