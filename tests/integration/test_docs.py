"""Pruebas de la documentación de la API: activa fuera de producción, apagada en producción."""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

DOC_PATHS = ["/docs", "/redoc", "/openapi.json"]


@pytest.mark.parametrize("path", DOC_PATHS)
def test_en_test_la_documentacion_esta_disponible(test_settings: Settings, path: str) -> None:
    client = TestClient(create_app(test_settings))

    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", DOC_PATHS)
def test_en_local_la_documentacion_esta_disponible(path: str) -> None:
    local_settings = Settings(
        _env_file=None, environment="local", database_url=SecretStr("sqlite://")
    )
    client = TestClient(create_app(local_settings))

    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", DOC_PATHS)
def test_en_produccion_la_documentacion_esta_desactivada(
    production_settings: Settings, path: str
) -> None:
    client = TestClient(create_app(production_settings))

    assert client.get(path).status_code == 404
