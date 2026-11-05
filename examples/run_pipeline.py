import json

from financial_ai_advisor_agents.app import build_application


app = build_application()
result = app.pipeline.run("筛选出 RSI 超卖且均线多头排列的股票，并说明筛选依据")
print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
