import argparse
import json
import sys

from financial_ai_advisor_agents.app import build_application
from financial_ai_advisor_agents.config import Settings
from financial_ai_advisor_agents.database.seed import initialize_database
from financial_ai_advisor_agents.database.schema_registry import SchemaRegistry


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="finagent", description="Multi-agent financial advisor educational demo")
    parser.add_argument("--mode", choices=["mock", "openai"], help="LLM provider mode")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser("pipeline", help="Run the four-stage pipeline")
    pipeline.add_argument("--query", required=True)
    pipeline.add_argument("--user-id", default="demo-user")

    database = subparsers.add_parser("database", help="Run the database QA workflow")
    database.add_argument("--query", required=True)
    database.add_argument("--user-id", default="demo-user")

    agent = subparsers.add_parser("agent", help="Run an agent independently")
    agent.add_argument("name", choices=["planner", "metric_extraction", "text2sql"])
    agent.add_argument("--query", required=True)
    agent.add_argument("--user-id", default="demo-user")

    subparsers.add_parser("init-data", help="Rebuild the Mock SQLite database")
    serve = subparsers.add_parser("serve", help="Run the HTTP API and Web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    try:
        settings = Settings.from_env(args.mode)
        if args.command == "init-data":
            registry = SchemaRegistry(settings.schema_path)
            initialize_database(settings.mock_data_path, settings.database_path, registry)
            output = {"database_path": str(settings.database_path), "status": "created"}
        else:
            app = build_application(settings)
            if args.command == "serve":
                import uvicorn

                from financial_ai_advisor_agents.api import create_api

                uvicorn.run(create_api(app), host=args.host, port=args.port)
                return 0
            output = _run_command(app, args)
        print(_json(output))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 1


def _run_command(app, args):
    if args.command == "pipeline":
        return app.pipeline.run(args.query, args.user_id)
    if args.command == "database":
        memory = app.pipeline.memory.context(args.user_id, app.settings.history_limit)
        return app.database_workflow.run(args.query, memory.history)
    memory = app.pipeline.memory.context(args.user_id, app.settings.history_limit)
    if args.name == "planner":
        return app.planner.run(args.query, memory)
    if args.name == "metric_extraction":
        return app.database_workflow.metric_extraction.run(args.query)
    rewritten = app.database_workflow.query_rewrite.run(args.query, memory.history)
    entities = app.database_workflow.metric_extraction.run(rewritten.rewritten_query)
    semantic = app.database_workflow.semantic_analysis.run(rewritten.rewritten_query, entities)
    return app.database_workflow.text2sql.run(semantic)


def _json(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
