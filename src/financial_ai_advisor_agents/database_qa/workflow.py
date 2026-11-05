from collections.abc import Sequence

from financial_ai_advisor_agents.schemas.database import DatabaseQAResult
from financial_ai_advisor_agents.schemas.memory import Message


class DatabaseQAWorkflow:
    def __init__(self, query_rewrite, dialogue_planner, metric_extraction, semantic_analysis, text2sql, sql_execution, postprocessing):
        self.query_rewrite = query_rewrite
        self.dialogue_planner = dialogue_planner
        self.metric_extraction = metric_extraction
        self.semantic_analysis = semantic_analysis
        self.text2sql = text2sql
        self.sql_execution = sql_execution
        self.postprocessing = postprocessing

    def run(self, query: str, history: Sequence[Message] = (), feedback: str = "") -> DatabaseQAResult:
        rewritten = self.query_rewrite.run(query, history)
        dialogue_plan = self.dialogue_planner.run(rewritten.rewritten_query)
        entities = self.metric_extraction.run(rewritten.rewritten_query)
        semantic = self.semantic_analysis.run(rewritten.rewritten_query, entities)
        text2sql = self.text2sql.run(semantic, feedback)
        query_result = self.sql_execution.run(text2sql)
        preferred = [item.column for item in semantic.aligned_entities]
        postprocess = self.postprocessing.run(query_result, preferred)
        return DatabaseQAResult(
            original_query=query,
            rewritten_query=rewritten.rewritten_query,
            dialogue_steps=dialogue_plan.steps,
            entities=entities,
            semantic=semantic,
            text2sql=text2sql,
            query_result=query_result,
            postprocess=postprocess,
        )
