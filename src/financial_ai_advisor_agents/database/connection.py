import sqlite3
from pathlib import Path

from financial_ai_advisor_agents.database.sql_guard import SQLGuard
from financial_ai_advisor_agents.schemas.database import QueryResult


class DatabaseQuery:
    def __init__(self, path: Path, guard: SQLGuard):
        self.path = path
        self.guard = guard

    def execute(self, sql: str) -> QueryResult:
        safe_sql = self.guard.validate(sql)
        if not self.path.exists():
            raise FileNotFoundError(f"Mock database not found: {self.path}. Run scripts/build_mock_data.py first.")
        connection = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute(safe_sql)
            columns = [item[0] for item in cursor.description or []]
            rows = [dict(row) for row in cursor.fetchmany(self.guard.max_rows + 1)]
        finally:
            connection.close()
        truncated = len(rows) > self.guard.max_rows
        rows = rows[: self.guard.max_rows]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), sql=safe_sql, truncated=truncated)
