"""Configuración común de las pruebas.

ENVIRONMENT se fija en "test" antes de que cualquier prueba importe `app`, para que la
configuración nunca lea el `.env` del desarrollador ni use valores de otro ambiente.
"""

import logging
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlmodel import Session, SQLModel

import app.models  # noqa: F401  (registra las tablas en SQLModel.metadata)

# app.config no tiene efectos al importarse; app.main sí (crea la app), por eso ninguna prueba
# lo importa a nivel de módulo antes de que se fije ENVIRONMENT aquí.
from app.config import Settings
from app.db import build_engine

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
    """Configuración del ambiente de pruebas, sin leer ningún archivo .env.

    La SECRET_KEY es fija para poder decodificar la cookie de sesión en las pruebas, y las
    credenciales de Google son ficticias: ninguna prueba llama a Google.
    """
    return Settings(
        _env_file=None,
        environment="test",
        secret_key=SecretStr("s" * 32),
        google_client_id="test-client-id",  # type: ignore[call-arg]
        google_client_secret=SecretStr("test-client-secret"),
        owner_emails="dueno@example.com",
    )


@pytest.fixture
def session() -> Iterator[Session]:
    """Sesión sobre SQLite en memoria con todas las tablas.

    `create_all` solo se usa en las pruebas; en la app las tablas las crea Alembic.
    """
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """Cliente HTTP de una app de pruebas con las tablas creadas en su base en memoria."""
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    application = create_app(test_settings)
    SQLModel.metadata.create_all(application.state.engine)
    with TestClient(application) as test_client:
        yield test_client


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
    # Login con Google (PED-15): credenciales ficticias; ninguna prueba llama a Google.
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OWNER_EMAILS", "dueno@example.com")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://pedidofacil-6nky.onrender.com")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    return Settings(_env_file=None)
