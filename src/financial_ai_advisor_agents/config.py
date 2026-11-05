import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent.parent
IS_SOURCE_TREE = (SOURCE_ROOT / "pyproject.toml").is_file()
RESOURCE_ROOT = SOURCE_ROOT if IS_SOURCE_TREE else PACKAGE_ROOT / "resources"
DEFAULT_RUNTIME_DIR = SOURCE_ROOT / "runtime" if IS_SOURCE_TREE else Path.cwd() / "runtime"


@dataclass(frozen=True)
class Settings:
    mode: str
    database_path: Path
    memory_path: Path
    chart_dir: Path
    prompt_dir: Path
    schema_path: Path
    mock_data_path: Path
    max_replans: int
    max_rows: int
    history_limit: int
    chart_enabled: bool
    openai_api_key: str
    openai_base_url: str
    openai_model: str

    @classmethod
    def from_env(cls, mode: str | None = None) -> "Settings":
        load_dotenv()
        app_config = yaml.safe_load((RESOURCE_ROOT / "configs" / "app.yaml").read_text(encoding="utf-8"))
        runtime = Path(os.getenv("FINAGENT_RUNTIME_DIR", str(DEFAULT_RUNTIME_DIR))).expanduser().resolve()
        selected_mode = (mode or os.getenv("APP_MODE", "mock")).lower()
        if selected_mode not in {"mock", "openai"}:
            raise ValueError("APP_MODE must be 'mock' or 'openai'")
        return cls(
            mode=selected_mode,
            database_path=runtime / "mock_advisor.db",
            memory_path=runtime / "memory.db",
            chart_dir=runtime / "charts",
            prompt_dir=RESOURCE_ROOT / "prompts",
            schema_path=RESOURCE_ROOT / "configs" / "finance_schema.yaml",
            mock_data_path=RESOURCE_ROOT / "data" / "mock" / "securities.csv",
            max_replans=int(os.getenv("FINAGENT_MAX_REPLANS", app_config["max_replans"])),
            max_rows=int(os.getenv("FINAGENT_MAX_ROWS", app_config["max_rows"])),
            history_limit=app_config["history_limit"],
            chart_enabled=app_config["chart_enabled"],
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
