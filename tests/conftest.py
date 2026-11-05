from dataclasses import replace

import pytest

from financial_ai_advisor_agents.app import build_application
from financial_ai_advisor_agents.config import Settings


@pytest.fixture
def settings(tmp_path):
    base = Settings.from_env("mock")
    return replace(
        base,
        database_path=tmp_path / "mock.db",
        memory_path=tmp_path / "memory.db",
        chart_dir=tmp_path / "charts",
        rag_index_path=tmp_path / "knowledge_index.json",
    )


@pytest.fixture
def app(settings):
    return build_application(settings)
