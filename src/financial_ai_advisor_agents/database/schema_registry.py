import re
from pathlib import Path
from typing import Any

import yaml

from financial_ai_advisor_agents.schemas.database import AlignedEntity, MetricEntity


class SchemaRegistry:
    def __init__(self, path: Path):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.table = config["table"]
        self.columns = config["columns"]
        self.entities = config["entities"]
        self.aliases = config.get("aliases", {})

    def canonical_name(self, name: str) -> str:
        return self.aliases.get(name, name)

    def extract_entities(self, query: str) -> list[MetricEntity]:
        normalized_query = self._normalize(query)
        names = set(self.entities) | set(self.aliases)
        found: list[tuple[int, MetricEntity]] = []
        occupied: list[tuple[int, int]] = []
        seen = set()
        for name in sorted(names, key=len, reverse=True):
            normalized_name = self._normalize(name)
            start = normalized_query.find(normalized_name)
            if start == -1:
                continue
            end = start + len(normalized_name)
            if any(start < other_end and end > other_start for other_start, other_end in occupied):
                continue
            canonical = self.canonical_name(name)
            if canonical in seen:
                continue
            definition = self.entities[canonical]
            found.append((start, MetricEntity(entity_name=canonical, entity_type=definition["entity_type"])))
            occupied.append((start, end))
            seen.add(canonical)
        return [entity for _, entity in sorted(found, key=lambda item: item[0])]

    def align(self, entities: list[MetricEntity], query: str) -> tuple[list[AlignedEntity], list[str]]:
        aligned = []
        unaligned = []
        for entity in entities:
            canonical = self.canonical_name(entity.entity_name)
            definition = self.entities.get(canonical)
            if not definition or definition["column"] not in self.columns:
                unaligned.append(entity.entity_name)
                continue
            operator, value = definition["operator"], definition["value"]
            if not operator:
                operator, value = self._extract_threshold(query, canonical)
            aligned.append(AlignedEntity(
                entity_name=entity.entity_name,
                canonical_name=canonical,
                table=self.table,
                column=definition["column"],
                operator=operator,
                value=value,
                datetime=entity.datetime,
                entity_type=entity.entity_type,
            ))
        return aligned, unaligned

    def minimal_schema(self, aligned: list[AlignedEntity]) -> str:
        columns = {"symbol", "name", "close", "trade_date"} | {item.column for item in aligned}
        definitions = [f"  {name} {self.columns[name]}" for name in self.columns if name in columns]
        return f"CREATE TABLE {self.table} (\n" + ",\n".join(definitions) + "\n);"

    def _extract_threshold(self, query: str, entity_name: str) -> tuple[str, Any]:
        normalized = self._normalize(query)
        entity = re.escape(self._normalize(entity_name))
        patterns = [
            (r"(?:不低于|大于等于|>=|≥)", ">="),
            (r"(?:不高于|小于等于|<=|≤)", "<="),
            (r"(?:低于|小于|<)", "<"),
            (r"(?:高于|大于|超过|>|以上)", ">"),
        ]
        for operator_pattern, operator in patterns:
            match = re.search(entity + operator_pattern + r"(\d+(?:\.\d+)?)%?", normalized)
            if match:
                return operator, float(match.group(1))
        return "", ""

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", "", value).upper()
