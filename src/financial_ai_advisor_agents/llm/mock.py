from typing import Any, TypeVar

from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.llm.structured_output import parse_structured
from financial_ai_advisor_agents.schemas.database import DialoguePlan, MetricEntity, QueryRewriteResult, Text2SQLResult
from financial_ai_advisor_agents.schemas.pipeline import ExecutorType, FinalResponse, Plan, TaskSpec, ValidationResult

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
        iteration = payload.get("iteration", 0)
        if any(word in query for word in ["持仓", "组合优化", "收益归因", "组合风险"]):
            return Plan(
                is_complex=True,
                reasoning_summary="识别到示例持仓分析需求，调用收益归因、风险诊断与组合优化工作流",
                tasks=[TaskSpec(
                    task_id="portfolio_1",
                    objective="分析虚构示例持仓并计算约束优化权重",
                    executor_name="portfolio_analysis",
                )],
                iteration=iteration,
            )
        if any(word in query for word in ["KYC", "kyc", "风险偏好", "风险画像", "资产配置", "配置方案"]):
            return Plan(
                is_complex=False,
                reasoning_summary="识别到KYC与画像需求，读取当前用户的问卷进度和配置状态",
                tasks=[TaskSpec(
                    task_id="kyc_1",
                    objective="返回五题KYC进度；完成后给出风险画像与配置",
                    executor_name="kyc",
                )],
                iteration=iteration,
            )
        if any(word in query for word in ["基本面", "多维指标", "估值评分", "综合评分"]):
            return Plan(
                is_complex=True,
                reasoning_summary="识别到金融小模型需求，计算虚构证券的横截面多维评分",
                tasks=[TaskSpec(
                    task_id="financial_1",
                    objective="计算估值、质量、技术、股息与综合评分",
                    executor_type=ExecutorType.FINANCIAL_MODEL,
                    executor_name="financial_models",
                )],
                iteration=iteration,
            )
        if any(word in query for word in ["知识库", "什么是", "为什么", "如何理解", "投资期限", "分散投资", "备用金"]):
            return Plan(
                is_complex=False,
                reasoning_summary="识别到金融教育问答需求，调用本地BM25检索与引用回答",
                tasks=[TaskSpec(
                    task_id="rag_1",
                    objective="检索本地虚构知识文档并生成有来源的教育回答",
                    executor_name="rag",
                )],
                iteration=iteration,
            )
        entities = self.registry.extract_entities(query)
        if not entities:
            return Plan(
                is_complex=False,
                reasoning_summary="当前问题未匹配已注册的数据库、持仓、KYC、RAG或金融模型能力",
                tasks=[],
                iteration=iteration,
            )
        task = TaskSpec(
            task_id="database_1",
            objective="完成指标抽取、Text2SQL、只读查询与数据后处理",
            executor_name="database_qa",
        )
        return Plan(
            is_complex=len(entities) > 1 or "分析" in query,
            reasoning_summary=f"识别到{len(entities)}个已注册指标实体",
            tasks=[task],
            iteration=iteration,
        )

    def _validate(self, payload: dict[str, Any]) -> ValidationResult:
        return ValidationResult(passed=True, checks=["LLM充分性检查（Mock规则）"], feedback="任务结果覆盖当前查询")

    def _synthesize(self, payload: dict[str, Any]) -> FinalResponse:
        results = payload.get("task_results", [])
        datasets = [item.get("data", {}) for item in results]
        portfolio = next((data for data in datasets if {"portfolio", "risk", "optimization"} <= data.keys()), None)
        if portfolio is not None:
            risk = portfolio["risk"]
            answer = (
                f"虚构示例持仓市值为 {portfolio['total_value']:.2f}，持有期收益率 {portfolio['total_return']:.2%}，"
                f"相对基准超额收益 {portfolio['active_return']:.2%}。风险等级为{risk['level']}"
                f"（{risk['score']:.1f}/100），年化波动率 {risk['annualized_volatility']:.2%}，"
                f"最大回撤 {risk['max_drawdown']:.2%}。已计算收益归因、诊断和约束优化权重。"
            )
            return FinalResponse(
                status="success",
                answer=answer,
                assumptions=portfolio["assumptions"],
                sources=[{
                    "kind": "portfolio",
                    "reference": "mock_portfolio",
                    "detail": {"holding_count": len(portfolio["holdings"]), "method": portfolio["optimization"]["method"]},
                }],
                warnings=["这是内置虚构示例持仓，不是用户真实账户，也不构成投资建议"],
            )

        kyc = next((data for data in datasets if {"answers", "completed", "question", "allocation"} <= data.keys()), None)
        if kyc is not None:
            if not kyc["completed"]:
                question = kyc["question"]
                options = "、".join(option["label"] for option in question["options"])
                answer = f"KYC 已完成 {len(kyc['answers'])}/5 题。下一题：{question['title']} 可选：{options}。"
                return FinalResponse(
                    status="success",
                    answer=answer,
                    assumptions=[],
                    warnings=["完成五题后才会生成风险画像与配置；当前结果不代表已完成风险测评"],
                )
            allocation = "、".join(f"{name} {weight}%" for name, weight in kyc["allocation"].items())
            return FinalResponse(
                status="success",
                answer=f"KYC 已完成，风险等级为{kyc['risk_level']}（{kyc['risk_score']}分）。示例配置：{allocation}。",
                assumptions=[
                    kyc["allocation_explanation"],
                    f"市场环境：{kyc['market_environment']['economic_cycle']}；{kyc['market_environment']['market_interest_rate']}。",
                ],
                warnings=["配置由本地规则生成，仅用于演示，不构成个性化投资建议"],
            )

        rag = next((data for data in datasets if {"query", "answer", "sources", "status"} <= data.keys()), None)
        if rag is not None:
            sources = [{
                "kind": "knowledge",
                "reference": f"{source['source']}#page={source['page']}",
                "detail": {"title": source["title"], "chunk_id": source["chunk_id"], "score": source["score"]},
            } for source in rag["sources"]]
            return FinalResponse(
                status="success" if rag["status"] == "ok" else "insufficient_evidence",
                answer=rag["answer"],
                sources=sources,
                warnings=["回答仅依据本地虚构金融教育文档，不连接外部知识库或实时行情"],
            )

        financial = next((data for data in datasets if "scores" in data), None)
        if financial is not None:
            leaders = financial["scores"][:3]
            ranking = "；".join(
                f"{item['name']}（{item['symbol']}）{item['total_score']:.2f}分"
                for item in leaders
            )
            return FinalResponse(
                status="success",
                answer=f"已完成 {len(financial['scores'])} 只虚构证券的多维评分，综合分前三为：{ranking}。",
                assumptions=["综合分由估值30%、质量30%、技术25%、股息15%加权，采用横截面Min-Max归一化。"],
                sources=[{"kind": "financial_model", "reference": "mock_securities_csv", "detail": {"count": len(financial["scores"])}}],
                warnings=["评分用于虚构样本的相对比较，不是评级、投资建议或未来收益预测"],
            )

        database_data = next((data for data in datasets if "query_result" in data), None)
        if database_data is None:
            return FinalResponse(
                status="unsupported",
                answer="当前问题超出已注册能力。可尝试清单内指标选股、示例持仓分析、KYC、金融知识问答或多维评分。",
                warnings=["未调用真实LLM或外部金融数据，未编造答案"],
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
        chart_url = database_data.get("postprocess", {}).get("chart_url", "")
        if chart_url:
            sources.append({"kind": "chart", "reference": chart_url, "detail": {}})
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
