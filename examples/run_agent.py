import argparse
import json

from financial_ai_advisor_agents.app import build_application


parser = argparse.ArgumentParser()
parser.add_argument("name", choices=["planner", "metric_extraction", "text2sql"])
parser.add_argument("--query", required=True)
args = parser.parse_args()
app = build_application()
memory = app.pipeline.memory.context("demo-user")
if args.name == "planner":
    result = app.planner.run(args.query, memory)
elif args.name == "metric_extraction":
    result = app.database_workflow.metric_extraction.run(args.query)
else:
    entities = app.database_workflow.metric_extraction.run(args.query)
    semantic = app.database_workflow.semantic_analysis.run(args.query, entities)
    result = app.database_workflow.text2sql.run(semantic)
if isinstance(result, list):
    output = [item.model_dump(mode="json") for item in result]
else:
    output = result.model_dump(mode="json")
print(json.dumps(output, ensure_ascii=False, indent=2))
