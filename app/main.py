"""Punto de entrada de la aplicación FastAPI."""

import logging
import sys
from typing import cast

from fastapi import FastAPI
from pydantic import SecretStr

from app import APP_NAME, __version__
from app.config import Settings, get_settings
from app.db import build_engine
from app.routers import health

LOGGER_NAME = "pedidofacil"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_logging(level: str) -> None:
    """Configura el logger de la app con su propio handler, sin depender de basicConfig.

    uvicorn (y pytest) ya instalan handlers en el logger raíz, lo que convierte a
    basicConfig en una operación sin efecto. El handler escribe en stdout, que Render
    captura, y el logger no propaga al raíz para no duplicar líneas.
    """
    app_logger = logging.getLogger(LOGGER_NAME)
    app_logger.setLevel(level)
    if not any(handler.get_name() == LOGGER_NAME for handler in app_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name(LOGGER_NAME)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        app_logger.addHandler(handler)
    app_logger.propagate = False


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea y configura la aplicación.

    Las pruebas pasan su propia configuración; en ejecución normal se lee del entorno.
    """
    if settings is None:
        settings = get_settings()
    # Settings completa log_level según el ambiente al validarse.
    _configure_logging(cast(str, settings.log_level))

    docs = settings.docs_enabled
    application = FastAPI(
        title=APP_NAME,
        version=__version__,
        # En producción no se publican la documentación ni el esquema de la API.
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    # Fuente única de configuración y motor para dependencias y routers.
    application.state.settings = settings
    # Único punto donde se lee la URL: Settings garantiza que existe tras validarse.
    database_url = cast(SecretStr, settings.database_url).get_secret_value()
    application.state.engine = build_engine(database_url)
    application.include_router(health.router)

    if settings.environment == "production" and settings.ai_provider == "fake":
        logger.warning(
            "Producción usa el proveedor de IA simulado (AI_PROVIDER=fake): "
            "los pedidos no se interpretan con Gemini."
        )
    logger.info(
        "Aplicación iniciada (entorno=%s, commit=%s)", settings.environment, settings.git_commit
    )
    return application


app = create_app()
