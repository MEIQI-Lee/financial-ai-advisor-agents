import json
import subprocess
import sys


def test_metric_extraction_cli():
    completed = subprocess.run(
        [sys.executable, "-m", "financial_ai_advisor_agents", "--mode", "mock", "agent", "metric_extraction", "--query", "RSI 超卖"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload[0]["entity_name"] == "RSI超卖"
    assert payload[0]["datetime"] == ""
