"""Punto de entrada de la aplicación FastAPI."""

import logging

from fastapi import FastAPI

from app import __version__
from app.config import get_settings

logger = logging.getLogger("pedidofacil")


def create_app() -> FastAPI:
    """Crea y configura la aplicación."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    application = FastAPI(title=settings.app_name, version=__version__)

    @application.get("/health", tags=["operación"])
    def health() -> dict[str, str]:
        """Health check: lo usa Render y muestra qué versión y commit están desplegados."""
        return {"status": "ok", "version": __version__, "commit": settings.git_commit[:7]}

    logger.info(
        "Aplicación iniciada (entorno=%s, commit=%s)", settings.environment, settings.git_commit
    )
    return application


app = create_app()
