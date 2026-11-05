from pathlib import Path
from statistics import mean
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from financial_ai_advisor_agents.schemas.database import PostProcessResult, QueryResult


class DataPostprocessingAgent:
    def __init__(self, chart_dir: Path, chart_enabled: bool = True):
        self.chart_dir = chart_dir
        self.chart_enabled = chart_enabled

    def run(self, result: QueryResult, preferred_columns: list[str] | None = None) -> PostProcessResult:
        numeric_averages = {}
        for column in result.columns:
            values = [row[column] for row in result.rows if isinstance(row.get(column), (int, float))]
            if values:
                numeric_averages[column] = round(mean(values), 4)
        summary = {
            "row_count": result.row_count,
            "symbols": [row.get("symbol") for row in result.rows],
            "numeric_averages": numeric_averages,
            "truncated": result.truncated,
        }
        chart_path = ""
        chart_url = ""
        if self.chart_enabled and result.rows:
            metric = self._chart_column(result, preferred_columns or [])
            if metric:
                path = self._create_chart(result, metric)
                chart_path = str(path)
                chart_url = f"/charts/{path.name}"
        return PostProcessResult(summary=summary, chart_path=chart_path, chart_url=chart_url)

    def _chart_column(self, result: QueryResult, preferred: list[str]) -> str:
        candidates = preferred + result.columns
        return next((column for column in candidates if column in result.columns and all(
            isinstance(row.get(column), (int, float)) for row in result.rows
        )), "")

    def _create_chart(self, result: QueryResult, metric: str) -> Path:
        self.chart_dir.mkdir(parents=True, exist_ok=True)
        path = self.chart_dir / f"query-{uuid4().hex}.png"
        labels = [str(row.get("symbol", index)) for index, row in enumerate(result.rows)]
        values = [row[metric] for row in result.rows]
        figure, axis = plt.subplots(figsize=(8, 4.5))
        axis.bar(labels, values, color="#167c68")
        axis.set_title("Mock query results")
        axis.set_ylabel(metric)
        axis.spines[["top", "right"]].set_visible(False)
        figure.tight_layout()
        figure.savefig(path, dpi=150)
        plt.close(figure)
        return path
