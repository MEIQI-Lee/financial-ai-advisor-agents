import sqlglot
from sqlglot import exp

from financial_ai_advisor_agents.core.errors import SQLValidationError
from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry


class SQLGuard:
    def __init__(self, registry: SchemaRegistry, max_rows: int = 50):
        self.registry = registry
        self.max_rows = max_rows

    def validate(self, sql: str) -> str:
        if not sql.strip() or "\x00" in sql:
            raise SQLValidationError("SQL is empty or contains invalid characters")
        try:
            statements = [item for item in sqlglot.parse(sql, read="sqlite") if item]
        except Exception as exc:
            raise SQLValidationError(f"SQL parsing failed: {exc}") from exc
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise SQLValidationError("Only one SELECT statement is allowed")
        statement = statements[0]
        if statement.find(exp.Into):
            raise SQLValidationError("SELECT INTO is not allowed")
        tables = list(statement.find_all(exp.Table))
        if not tables:
            raise SQLValidationError("A registered table is required")
        for table in tables:
            if table.name != self.registry.table or table.db or table.catalog:
                raise SQLValidationError(f"Unregistered table: {table.sql()}")
        for column in statement.find_all(exp.Column):
            if column.name not in self.registry.columns:
                raise SQLValidationError(f"Unregistered column: {column.name}")
        limit = statement.args.get("limit")
        if limit is None:
            statement = statement.limit(self.max_rows)
        else:
            try:
                value = int(limit.expression.name)
            except (ValueError, AttributeError) as exc:
                raise SQLValidationError("LIMIT must be an integer") from exc
            if value <= 0:
                raise SQLValidationError("LIMIT must be positive")
            if value > self.max_rows:
                statement = statement.limit(self.max_rows)
        return statement.sql(dialect="sqlite")
