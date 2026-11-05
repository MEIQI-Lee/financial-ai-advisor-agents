from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    id: str
    title: str
    content: str
    source: str
    page: int
    tags: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    chunk_id: str
    title: str
    text: str
    source: str
    page: int
    tags: list[str] = Field(default_factory=list)
    score: float


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str
