"""Configuración común de las pruebas.

ENVIRONMENT se fija en "test" antes de que cualquier prueba importe `app`, para que la
configuración nunca lea el `.env` del desarrollador ni use valores de otro ambiente.
"""

import logging
import os
from collections.abc import Iterator

import pytest

# app.config no tiene efectos al importarse; app.main sí (crea la app), por eso ninguna prueba
# lo importa a nivel de módulo antes de que se fije ENVIRONMENT aquí.
from app.config import Settings

os.environ["ENVIRONMENT"] = "test"


@pytest.fixture(autouse=True)
def restore_app_log_level() -> Iterator[None]:
    """Restaura el logger de la app: `create_app` cambia su nivel, handlers y propagación,
    que son estado global del proceso."""
    app_logger = logging.getLogger("pedidofacil")
    previous_level = app_logger.level
    previous_handlers = list(app_logger.handlers)
    previous_propagate = app_logger.propagate
    yield
    app_logger.setLevel(previous_level)
    app_logger.handlers = previous_handlers
    app_logger.propagate = previous_propagate


@pytest.fixture
def app_log(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """`caplog` conectado al logger de la app.

    El logger `pedidofacil` no propaga al raíz (tiene su propio handler), así que el handler
    de `caplog`, que vive en el raíz, no vería sus mensajes.
    """
    app_logger = logging.getLogger("pedidofacil")
    app_logger.addHandler(caplog.handler)
    yield caplog
    app_logger.removeHandler(caplog.handler)


@pytest.fixture
def test_settings() -> Settings:
    """Configuración del ambiente de pruebas, sin leer ningún archivo .env."""
    return Settings(_env_file=None, environment="test")


@pytest.fixture
def production_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Configuración de producción válida, con el proveedor de IA simulado.

    Crear el motor de PostgreSQL a partir de esta URL no abre ninguna conexión.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://usuario:clave@host/db")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return Settings(_env_file=None)
