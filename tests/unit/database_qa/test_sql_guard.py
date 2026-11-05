import pytest

from financial_ai_advisor_agents.core.errors import SQLValidationError
from financial_ai_advisor_agents.database.sql_guard import SQLGuard


@pytest.mark.parametrize("sql", [
    "DELETE FROM mock_securities",
    "SELECT * FROM mock_securities; DROP TABLE mock_securities",
    "SELECT * FROM secret_table",
    "SELECT secret_column FROM mock_securities",
    "SELECT * FROM mock_securities INTO backup",
])
def test_guard_rejects_unsafe_sql(app, sql):
    guard = SQLGuard(app.schema_registry, 50)
    with pytest.raises(SQLValidationError):
        guard.validate(sql)


def test_guard_adds_and_clamps_limit(app):
    guard = SQLGuard(app.schema_registry, 50)
    assert "LIMIT 50" in guard.validate("SELECT symbol FROM mock_securities").upper()
    assert "LIMIT 50" in guard.validate("SELECT symbol FROM mock_securities LIMIT 500").upper()
