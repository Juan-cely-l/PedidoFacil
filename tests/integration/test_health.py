"""Pruebas de los health checks: /health (con base de datos) y /health/live (sin base)."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import __version__
from app.config import Settings
from app.db import get_session
from app.main import create_app
from tests.doubles import FailingSession

FULL_COMMIT = "a1b2c3d4e5f6"


def _failing_session() -> Iterator[Session]:
    yield FailingSession()


def _with_failing_database(application: FastAPI) -> FastAPI:
    application.dependency_overrides[get_session] = _failing_session
    return application


def test_la_prueba_de_humo_sigue_respondiendo() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_con_la_base_disponible_responde_200(test_settings: Settings) -> None:
    client = TestClient(create_app(test_settings))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "version": __version__,
        "commit": "local",
    }


def test_health_con_la_base_caida_responde_503(test_settings: Settings) -> None:
    client = TestClient(_with_failing_database(create_app(test_settings)))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "database": "error",
        "version": __version__,
        "commit": "local",
    }


def test_el_503_no_expone_detalles_de_la_falla(test_settings: Settings) -> None:
    client = TestClient(_with_failing_database(create_app(test_settings)))

    body = client.get("/health").text

    for detail in ("usuario:clave", "postgresql://", "OperationalError", "SELECT 1"):
        assert detail not in body


def test_health_live_responde_200_sin_tocar_la_base(test_settings: Settings) -> None:
    application = create_app(test_settings)
    calls: list[str] = []

    def session_that_must_not_be_used() -> Iterator[Session]:
        calls.append("get_session")
        yield FailingSession()

    application.dependency_overrides[get_session] = session_that_must_not_be_used
    client = TestClient(application)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "commit": "local"}
    assert calls == []


def test_health_live_sigue_respondiendo_200_con_la_base_caida(test_settings: Settings) -> None:
    # Requisito real: Render no debe reiniciar la app por una falla de la base de datos.
    client = TestClient(_with_failing_database(create_app(test_settings)))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize("path", ["/health", "/health/live"])
def test_los_health_checks_muestran_el_commit_corto(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", FULL_COMMIT)
    settings = Settings(_env_file=None, environment="test")
    client = TestClient(create_app(settings))

    response = client.get(path)

    assert response.json()["commit"] == "a1b2c3d"
