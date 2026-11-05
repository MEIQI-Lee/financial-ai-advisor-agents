from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry
from financial_ai_advisor_agents.schemas.database import MetricEntity, SemanticAnalysisResult


class SemanticAnalysisAgent:
    def __init__(self, registry: SchemaRegistry):
        self.registry = registry

    def run(self, query: str, entities: list[MetricEntity]) -> SemanticAnalysisResult:
        aligned, unaligned = self.registry.align(entities, query)
        return SemanticAnalysisResult(
            rewritten_query=query,
            aligned_entities=aligned,
            schema_text=self.registry.minimal_schema(aligned),
            unaligned_entities=unaligned,
        )
