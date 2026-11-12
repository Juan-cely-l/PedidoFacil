"""Punto de entrada de la aplicación FastAPI."""

import logging
from typing import cast

from fastapi import FastAPI
from pydantic import SecretStr

from app import APP_NAME, __version__
from app.config import Settings, get_settings
from app.db import build_engine
from app.routers import health

logger = logging.getLogger("pedidofacil")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea y configura la aplicación.

    Las pruebas pasan su propia configuración; en ejecución normal se lee del entorno.
    """
    if settings is None:
        settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    application = FastAPI(title=APP_NAME, version=__version__)
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
