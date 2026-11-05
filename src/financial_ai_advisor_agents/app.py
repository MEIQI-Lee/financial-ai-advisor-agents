from dataclasses import dataclass

from financial_ai_advisor_agents.agents.executor import ExecutionAgent
from financial_ai_advisor_agents.agents.planner import PlanningAgent
from financial_ai_advisor_agents.agents.synthesizer import SynthesisAgent
from financial_ai_advisor_agents.agents.validator import ValidationAgent
from financial_ai_advisor_agents.config import Settings
from financial_ai_advisor_agents.core.prompt_loader import PromptLoader
from financial_ai_advisor_agents.database.connection import DatabaseQuery
from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry
from financial_ai_advisor_agents.database.seed import initialize_database
from financial_ai_advisor_agents.database.sql_guard import SQLGuard
from financial_ai_advisor_agents.database_qa.dialogue_planner_agent import DialoguePlanningAgent
from financial_ai_advisor_agents.database_qa.metric_extraction_agent import MetricEntityExtractionAgent
from financial_ai_advisor_agents.database_qa.postprocessing_agent import DataPostprocessingAgent
from financial_ai_advisor_agents.database_qa.query_rewrite_agent import QueryRewriteAgent
from financial_ai_advisor_agents.database_qa.semantic_analysis_agent import SemanticAnalysisAgent
from financial_ai_advisor_agents.database_qa.sql_execution_agent import SQLExecutionAgent
from financial_ai_advisor_agents.database_qa.text2sql_agent import Text2SQLAgent
from financial_ai_advisor_agents.database_qa.workflow import DatabaseQAWorkflow
from financial_ai_advisor_agents.llm import create_llm
from financial_ai_advisor_agents.llm.base import StructuredLLM
from financial_ai_advisor_agents.financial_models.suite import FinancialModelSuite
from financial_ai_advisor_agents.kyc.workflow import KYCWorkflow
from financial_ai_advisor_agents.memory.store import MemoryStore
from financial_ai_advisor_agents.portfolio.service import PortfolioService
from financial_ai_advisor_agents.rag.index import LocalBM25Index
from financial_ai_advisor_agents.rag.workflow import RAGWorkflow
from financial_ai_advisor_agents.schemas.pipeline import ExecutorType
from financial_ai_advisor_agents.tools.registry import CapabilityRegistry
from financial_ai_advisor_agents.workflows.pipeline import FourStagePipeline


@dataclass
class Application:
    settings: Settings
    schema_registry: SchemaRegistry
    llm: StructuredLLM
    database_workflow: DatabaseQAWorkflow
    capabilities: CapabilityRegistry
    pipeline: FourStagePipeline
    planner: PlanningAgent
    executor: ExecutionAgent
    validator: ValidationAgent
    synthesizer: SynthesisAgent
    memory: MemoryStore
    portfolio_service: PortfolioService
    financial_models: FinancialModelSuite
    kyc_workflow: KYCWorkflow
    rag_index: LocalBM25Index
    rag_workflow: RAGWorkflow


def build_application(settings: Settings | None = None, mode: str | None = None) -> Application:
    settings = settings or Settings.from_env(mode)
    schema_registry = SchemaRegistry(settings.schema_path)
    if not settings.database_path.exists():
        initialize_database(settings.mock_data_path, settings.database_path, schema_registry)
    prompts = PromptLoader(settings.prompt_dir)
    llm = create_llm(settings, schema_registry)
    guard = SQLGuard(schema_registry, settings.max_rows)
    database = DatabaseQuery(settings.database_path, guard)
    database_workflow = DatabaseQAWorkflow(
        QueryRewriteAgent(llm, prompts),
        DialoguePlanningAgent(llm, prompts),
        MetricEntityExtractionAgent(llm, prompts),
        SemanticAnalysisAgent(schema_registry),
        Text2SQLAgent(llm, prompts, settings.max_rows),
        SQLExecutionAgent(database),
        DataPostprocessingAgent(settings.chart_dir, settings.chart_enabled),
    )
    memory = MemoryStore(settings.memory_path)
    portfolio_service = PortfolioService(settings.portfolio_data_path)
    financial_models = FinancialModelSuite(settings.mock_data_path)
    kyc_workflow = KYCWorkflow(memory)
    rag_index = LocalBM25Index(settings.knowledge_data_path, settings.rag_index_path)
    if not settings.rag_index_path.exists():
        rag_index.build()
    rag_workflow = RAGWorkflow(rag_index)
    capabilities = CapabilityRegistry()

    def database_handler(task, context):
        query = task.input_bindings.get("query", context["query"])
        history = context["memory"].history
        feedback = task.input_bindings.get("feedback", "")
        return database_workflow.run(query, history, feedback).model_dump(mode="json")

    capabilities.register(
        "database_qa",
        ExecutorType.WORKFLOW,
        "指标实体抽取、语义对齐、Text2SQL、只读SQLite查询和图表后处理",
        database_handler,
    )
    capabilities.register(
        "portfolio_analysis",
        ExecutorType.WORKFLOW,
        "示例持仓的市值权重、收益归因、风险诊断与约束组合优化",
        lambda task, context: portfolio_service.analyze_sample().model_dump(mode="json"),
    )
    capabilities.register(
        "kyc",
        ExecutorType.WORKFLOW,
        "五题KYC状态、风险画像与可解释资产配置",
        lambda task, context: kyc_workflow.status(context["memory"].user_id).model_dump(mode="json"),
    )
    capabilities.register(
        "rag",
        ExecutorType.WORKFLOW,
        "本地BM25知识索引检索与带引用的教育回答",
        lambda task, context: rag_workflow.run(context["query"]).model_dump(mode="json"),
    )
    capabilities.register(
        "financial_models",
        ExecutorType.FINANCIAL_MODEL,
        "虚构证券的估值、质量、技术、股息评分与基本面风险标记",
        lambda task, context: {"scores": [item.model_dump(mode="json") for item in financial_models.score_securities()]},
    )
    planner = PlanningAgent(llm, prompts, capabilities)
    executor = ExecutionAgent(capabilities)
    validator = ValidationAgent(llm, prompts)
    synthesizer = SynthesisAgent(llm, prompts)
    pipeline = FourStagePipeline(
        planner,
        executor,
        validator,
        synthesizer,
        memory,
        settings.max_replans,
        settings.history_limit,
    )
    return Application(
        settings=settings,
        schema_registry=schema_registry,
        llm=llm,
        database_workflow=database_workflow,
        capabilities=capabilities,
        pipeline=pipeline,
        planner=planner,
        executor=executor,
        validator=validator,
        synthesizer=synthesizer,
        memory=memory,
        portfolio_service=portfolio_service,
        financial_models=financial_models,
        kyc_workflow=kyc_workflow,
        rag_index=rag_index,
        rag_workflow=rag_workflow,
    )
