import pytest
from fastapi.testclient import TestClient

from financial_ai_advisor_agents.api import create_api
from financial_ai_advisor_agents.kyc.workflow import KYC_QUESTIONS


ANSWERS = {
    "investment_experience": "professional",
    "loss_reaction": "buy_more",
    "fixed_expense_destination": "insurance_savings",
    "fixed_expense_ratio": "under_20",
    "investment_horizon": "over_10_years",
}


@pytest.fixture
def client(app):
    with TestClient(create_api(app)) as test_client:
        yield test_client


def test_health_capabilities_and_static_web(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["data"] == "fictional-mock"
    assert set(health.json()["services"]) == {
        "pipeline", "database", "portfolio", "kyc", "rag", "financial_models"
    }

    capabilities = client.get("/api/models/capabilities")
    assert capabilities.status_code == 200
    assert "financial_models" in capabilities.json()

    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "LOCAL API" in page.text


def test_database_and_pipeline_endpoints(client):
    database = client.post("/api/database", json={"query": "RSI 超卖", "user_id": "api-user"})
    assert database.status_code == 200
    assert database.json()["query_result"]["row_count"] == 3
    chart_url = database.json()["postprocess"]["chart_url"]
    assert chart_url.startswith("/charts/")
    assert client.get(chart_url).status_code == 200

    pipeline = client.post("/api/pipeline", json={"query": "分析示例持仓", "user_id": "api-user"})
    assert pipeline.status_code == 200
    assert pipeline.json()["final"]["status"] == "success"
    assert pipeline.json()["task_results"][0]["data"]["risk"]["score"] >= 0


def test_portfolio_sample_analyze_and_upload_validation(client):
    sample_response = client.get("/api/portfolio/sample")
    assert sample_response.status_code == 200
    sample = sample_response.json()
    assert len(sample["holdings"]) == 5
    assert sum(sample["optimization"]["weights"].values()) == pytest.approx(1.0)

    analyzed = client.post("/api/portfolio/analyze", json=sample["portfolio"])
    assert analyzed.status_code == 200
    assert analyzed.json()["total_value"] == pytest.approx(sample["total_value"])

    rejected = client.post(
        "/api/portfolio/upload",
        files={"file": ("holdings.txt", b"not an image", "text/plain")},
    )
    assert rejected.status_code == 415


def test_kyc_api_completes_and_recovers_profile(client):
    started = client.post("/api/kyc/start", json={"user_id": "api-kyc"})
    assert started.status_code == 200
    assert started.json()["step"] == 0

    for question in KYC_QUESTIONS:
        response = client.post("/api/kyc/answer", json={
            "user_id": "api-kyc",
            "question_id": question.id,
            "value": ANSWERS[question.id],
        })
        assert response.status_code == 200

    completed = response.json()
    assert completed["completed"] is True
    assert completed["risk_level"] == "积极"
    assert sum(completed["allocation"].values()) == 100
    assert set(completed["market_environment"]) == {
        "economic_cycle", "market_interest_rate", "policies_and_regulations"
    }

    restored = client.get("/api/kyc/status", params={"user_id": "api-kyc"})
    assert restored.status_code == 200
    assert restored.json()["answers"] == ANSWERS
    assert restored.json()["allocation"] == completed["allocation"]


def test_rag_api_returns_citations_and_handles_missing_evidence(client):
    response = client.post("/api/rag", json={"query": "什么是最大回撤", "top_k": 2})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["sources"]
    assert result["sources"][0]["source"]
    assert "[1]" in result["answer"]

    missing = client.post("/api/rag", json={"query": "量子计算硬件拓扑"})
    assert missing.status_code == 200
    assert missing.json()["status"] == "insufficient_evidence"
    assert missing.json()["sources"] == []


def test_financial_model_endpoints_and_error_contract(client):
    scores = client.get("/api/financial/scores")
    assert scores.status_code == 200
    assert len(scores.json()) == 6
    symbol = scores.json()[0]["symbol"]

    report = client.get(f"/api/financial/fundamental/{symbol.lower()}")
    assert report.status_code == 200
    assert report.json()["symbol"] == symbol
    assert report.json()["score"]["components"]

    unknown = client.get("/api/financial/fundamental/NOT_THERE")
    assert unknown.status_code == 400
    assert "unknown security symbol" in unknown.json()["detail"]
