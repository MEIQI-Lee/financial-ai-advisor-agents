from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from financial_ai_advisor_agents.app import Application, build_application
from financial_ai_advisor_agents.schemas.portfolio import Portfolio


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    user_id: str = "demo-user"


class UserRequest(BaseModel):
    user_id: str = "demo-user"


class KYCAnswerRequest(BaseModel):
    user_id: str = "demo-user"
    question_id: str
    value: str


class RAGRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)


def create_api(application: Application | None = None) -> FastAPI:
    application = application or build_application()
    api = FastAPI(
        title="Financial AI Advisor Agents API",
        version="0.2.0",
        description="Local educational API using deterministic models and fictional data.",
    )
    api.state.application = application

    @api.exception_handler(ValueError)
    async def handle_value_error(_, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @api.exception_handler(RuntimeError)
    async def handle_runtime_error(_, exc: RuntimeError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @api.get("/api/health")
    def health():
        return {
            "status": "ok",
            "mode": application.settings.mode,
            "data": "fictional-mock",
            "services": ["pipeline", "database", "portfolio", "kyc", "rag", "financial_models"],
        }

    @api.post("/api/pipeline")
    def pipeline(request: QueryRequest):
        return application.pipeline.run(request.query.strip(), request.user_id).model_dump(mode="json")

    @api.post("/api/database")
    def database(request: QueryRequest):
        memory = application.pipeline.memory.context(request.user_id, application.settings.history_limit)
        return application.database_workflow.run(request.query.strip(), memory.history).model_dump(mode="json")

    @api.get("/api/portfolio/sample")
    def portfolio_sample():
        return application.portfolio_service.analyze_sample().model_dump(mode="json")

    @api.post("/api/portfolio/analyze")
    def portfolio_analyze(portfolio: Portfolio):
        return application.portfolio_service.analyze(portfolio).model_dump(mode="json")

    @api.post("/api/portfolio/upload")
    async def portfolio_upload(file: UploadFile = File(...)):
        if file.content_type not in {"image/png", "image/jpeg"}:
            raise HTTPException(status_code=415, detail="Only PNG and JPEG images are supported")
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image size must not exceed 10 MB")
        return application.portfolio_service.analyze_image(content, Path(file.filename or "upload.png").name).model_dump(mode="json")

    @api.get("/api/financial/scores")
    def financial_scores():
        return [item.model_dump(mode="json") for item in application.financial_models.score_securities()]

    @api.get("/api/financial/fundamental/{symbol}")
    def fundamental(symbol: str):
        return application.financial_models.fundamental(symbol).model_dump(mode="json")

    @api.post("/api/kyc/start")
    def kyc_start(request: UserRequest):
        return application.kyc_workflow.start(request.user_id).model_dump(mode="json")

    @api.get("/api/kyc/status")
    def kyc_status(user_id: str = "demo-user"):
        return application.kyc_workflow.status(user_id).model_dump(mode="json")

    @api.post("/api/kyc/answer")
    def kyc_answer(request: KYCAnswerRequest):
        return application.kyc_workflow.answer(request.user_id, request.question_id, request.value).model_dump(mode="json")

    @api.post("/api/rag")
    def rag(request: RAGRequest):
        return application.rag_workflow.run(request.query.strip(), request.top_k, tags=request.tags).model_dump(mode="json")

    @api.get("/api/models/capabilities")
    def capabilities():
        return application.capabilities.descriptions()

    charts = application.settings.chart_dir
    charts.mkdir(parents=True, exist_ok=True)
    api.mount("/charts", StaticFiles(directory=charts), name="charts")
    web_dir = application.settings.web_dir
    if not web_dir.is_dir():
        raise RuntimeError(f"Web assets not found: {web_dir}")
    api.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return api
