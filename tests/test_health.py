"""Prueba humo: la aplicación arranca y el health check responde."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_responde_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
