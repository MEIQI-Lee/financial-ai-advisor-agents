from typing import Any, TypeVar

from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.llm.structured_output import parse_structured
from financial_ai_advisor_agents.schemas.database import DialoguePlan, MetricEntity, QueryRewriteResult, Text2SQLResult
from financial_ai_advisor_agents.schemas.pipeline import FinalResponse, Plan, TaskSpec, ValidationResult

T = TypeVar("T")


class MockLLM(StructuredLLM):
    def __init__(self, registry: SchemaRegistry):
        self.registry = registry

    def generate_json(self, operation: str, prompt: str, payload: dict[str, Any], schema: type[T]) -> T:
        handlers = {
            "main_planner": self._plan,
            "main_validator": self._validate,
            "main_synthesizer": self._synthesize,
            "query_rewrite": self._rewrite,
            "dialogue_planner": self._dialogue_plan,
            "metric_extraction": self._extract_metrics,
            "text2sql": self._text2sql,
        }
        if operation not in handlers:
            raise ValueError(f"Mock LLM does not support operation: {operation}")
        return parse_structured(handlers[operation](payload), schema)

    def _plan(self, payload: dict[str, Any]) -> Plan:
        query = payload["query"]
        entities = self.registry.extract_entities(query)
        if not entities:
            return Plan(is_complex=False, reasoning_summary="当前已注册能力仅支持清单内指标的数据库问答", tasks=[], iteration=payload.get("iteration", 0))
        task = TaskSpec(
            task_id="database_1",
            objective="完成指标抽取、Text2SQL、只读查询与数据后处理",
            executor_name="database_qa",
        )
        return Plan(
            is_complex=len(entities) > 1 or "分析" in query,
            reasoning_summary=f"识别到{len(entities)}个已注册指标实体",
            tasks=[task],
            iteration=payload.get("iteration", 0),
        )

    def _validate(self, payload: dict[str, Any]) -> ValidationResult:
        return ValidationResult(passed=True, checks=["LLM充分性检查（Mock规则）"], feedback="任务结果覆盖当前查询")

    def _synthesize(self, payload: dict[str, Any]) -> FinalResponse:
        results = payload.get("task_results", [])
        database_data = next((item.get("data", {}) for item in results if "query_result" in item.get("data", {})), None)
        if database_data is None:
            return FinalResponse(
                status="unsupported",
                answer="当前后端已实现清单内金融指标的数据库问答。持仓、KYC 和 RAG 仍处于待实现阶段。",
                warnings=["未调用真实LLM或外部金融数据"],
            )
        query_result = database_data["query_result"]
        rows = query_result["rows"]
        entities = database_data.get("entities", [])
        names = "、".join(f"{row['name']}（{row['symbol']}）" for row in rows)
        answer = f"查询到 {len(rows)} 只符合条件的 Mock 股票：{names}。" if rows else "没有找到符合全部条件的 Mock 股票。"
        assumptions = [
            f"{item['canonical_name']}：{item['column']} {item['operator']} {item['value']}"
            for item in database_data.get("semantic", {}).get("aligned_entities", [])
            if item.get("operator")
        ]
        sources = [
            {
                "kind": "sql",
                "reference": "mock_securities",
                "detail": {"sql": query_result["sql"], "row_count": query_result["row_count"]},
            }
        ]
        chart_path = database_data.get("postprocess", {}).get("chart_path", "")
        if chart_path:
            sources.append({"kind": "chart", "reference": chart_path, "detail": {}})
        return FinalResponse(
            status="success",
            answer=answer,
            assumptions=assumptions or [f"识别指标：{item['entity_name']}" for item in entities],
            sources=sources,
            warnings=["全部证券与指标均为虚构 Mock 数据，不构成投资建议"],
        )

    def _rewrite(self, payload: dict[str, Any]) -> QueryRewriteResult:
        query = payload["query"]
        return QueryRewriteResult(original_query=query, rewritten_query=query, reasoning_summary="Mock模式保留原始查询，不猜测省略信息")

    def _dialogue_plan(self, payload: dict[str, Any]) -> DialoguePlan:
        query = payload["query"]
        return DialoguePlan(
            steps=["指标实体抽取", "实体对齐与Schema拼接", "Text2SQL", "SQL执行", "数据后处理"],
            requires_chart=any(word in query for word in ["图", "图表", "走势", "对比"]),
        )

    def _extract_metrics(self, payload: dict[str, Any]) -> list[MetricEntity]:
        return self.registry.extract_entities(payload["query"])

    def _text2sql(self, payload: dict[str, Any]) -> Text2SQLResult:
        semantic = payload["semantic"]
        aligned = semantic["aligned_entities"]
        table = self.registry.table
        columns = ["symbol", "name", "close", "trade_date"]
        for item in aligned:
            if item["column"] not in columns:
                columns.append(item["column"])
        conditions = []
        for item in aligned:
            if not item["operator"]:
                continue
            value = item["value"]
            if isinstance(value, str) and value in self.registry.columns:
                rendered = value
            elif isinstance(value, str):
                rendered = "'" + value.replace("'", "''") + "'"
            else:
                rendered = str(value)
            conditions.append(f"{item['column']} {item['operator']} {rendered}")
        sql = f"SELECT {', '.join(columns)} FROM {table}"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        numeric = next((item["column"] for item in aligned if isinstance(item["value"], (int, float))), "symbol")
        sql += f" ORDER BY {numeric} ASC LIMIT {payload['max_rows']}"
        return Text2SQLResult(sql=sql, rationale="Mock模式根据已对齐实体确定性生成SQL", tables=[table])
