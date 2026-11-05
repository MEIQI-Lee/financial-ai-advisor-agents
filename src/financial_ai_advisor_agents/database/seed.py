import csv
import sqlite3
from pathlib import Path

from financial_ai_advisor_agents.config import Settings
from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry


def initialize_database(csv_path: Path, database_path: Path, registry: SchemaRegistry) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()
    columns = []
    for name, data_type in registry.columns.items():
        columns.append(f"{name} {data_type}")
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(f"CREATE TABLE {registry.table} ({', '.join(columns)})")
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        names = list(registry.columns)
        values = []
        for row in rows:
            values.append(tuple(_convert(row[name], registry.columns[name]) for name in names))
        placeholders = ", ".join("?" for _ in names)
        connection.executemany(f"INSERT INTO {registry.table} ({', '.join(names)}) VALUES ({placeholders})", values)
        connection.commit()
    finally:
        connection.close()


def _convert(value: str, data_type: str) -> str | float | int:
    if data_type == "REAL":
        return float(value)
    if data_type == "INTEGER":
        return int(value)
    return value


def initialize_default_database() -> Path:
    settings = Settings.from_env()
    registry = SchemaRegistry(settings.schema_path)
    initialize_database(settings.mock_data_path, settings.database_path, registry)
    return settings.database_path
