"""Punto de entrada de la aplicación FastAPI."""

import logging

from fastapi import FastAPI

from app import APP_NAME, __version__
from app.config import Settings, get_settings

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
    # Fuente única de configuración para dependencias y routers.
    application.state.settings = settings

    @application.get("/health", tags=["operación"])
    def health() -> dict[str, str]:
        """Health check: lo usa Render y muestra qué versión y commit están desplegados."""
        return {"status": "ok", "version": __version__, "commit": settings.git_commit[:7]}

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
