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


def test_rejects_non_amazon_url() -> None:
    response = client.post("/api/jobs", json={"url": "https://example.com/dp/B0CXT9RSGQ"})

    assert response.status_code == 422
    assert "Amazon" in response.json()["detail"]

