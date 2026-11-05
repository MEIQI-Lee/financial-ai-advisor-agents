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
from financial_ai_advisor_agents.memory.store import MemoryStore
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
    planner = PlanningAgent(llm, prompts, capabilities)
    executor = ExecutionAgent(capabilities)
    validator = ValidationAgent(llm, prompts)
    synthesizer = SynthesisAgent(llm, prompts)
    memory = MemoryStore(settings.memory_path)
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
        settings,
        schema_registry,
        llm,
        database_workflow,
        capabilities,
        pipeline,
        planner,
        executor,
        validator,
        synthesizer,
    )
