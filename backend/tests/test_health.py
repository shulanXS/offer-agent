from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthcheck_is_available() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Offer Agent"}


def test_v2_healthcheck_is_removed() -> None:
    response = client.get("/api/v2/healthz")

    assert response.status_code == 404
