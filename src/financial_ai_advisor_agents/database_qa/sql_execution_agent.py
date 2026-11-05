from financial_ai_advisor_agents.database.connection import DatabaseQuery
from financial_ai_advisor_agents.schemas.database import QueryResult, Text2SQLResult


class SQLExecutionAgent:
    def __init__(self, database: DatabaseQuery):
        self.database = database

    def run(self, text2sql: Text2SQLResult) -> QueryResult:
        return self.database.execute(text2sql.sql)
