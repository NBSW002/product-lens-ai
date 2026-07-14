from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_demo_mode() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["mode"] == "demo"


def test_create_and_read_analysis_job() -> None:
    created = client.post(
        "/api/jobs",
        json={"url": "https://www.amazon.com/dp/B0CXT9RSGQ"},
    )

    assert created.status_code == 202
    job_id = created.json()["id"]

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"running", "completed"}
    assert [event["stage"] for event in payload["trace_events"]] == [
        "PRODUCT_FETCH",
        "VISION_ANALYSIS",
        "TEXT_DRAFT",
        "QUALITY_CHECK",
        "TEXT_REVISION",
        "FINALIZE",
    ]
    assert payload["trace_events"][0]["output"]["asin"] == "B0CXT9RSGQ"
    assert payload["trace_events"][-1]["status"] == "completed"
    serialized = json.dumps(payload["trace_events"], ensure_ascii=False).lower()
    assert "authorization" not in serialized
    assert "api_key" not in serialized


def test_rejects_non_amazon_url() -> None:
    response = client.post("/api/jobs", json={"url": "https://example.com/dp/B0CXT9RSGQ"})

    assert response.status_code == 422
    assert "Amazon" in response.json()["detail"]
import json

