"""Punto de entrada de la aplicación FastAPI."""

import logging
import sys
from typing import Literal, cast

from fastapi import Depends, FastAPI
from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app import APP_NAME, __version__
from app.config import Settings, get_settings
from app.db import build_engine
from app.errors import handle_database_error
from app.routers import auth, catalog, health, quotes
from app.security import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    LoginRequired,
    redirect_to_login,
    require_owner,
)
from app.services.identity import GoogleIdentityProvider
from app.services.quote_ai import build_quote_agent

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
        # Denegar por defecto: toda ruta, presente o futura, exige la sesión del dueño salvo
        # las de PUBLIC_PATHS (research.md R1).
        dependencies=[Depends(require_owner)],
    )
    application.add_exception_handler(LoginRequired, redirect_to_login)
    # Solo SQLAlchemy, nunca Exception: un error de programación no se disfraza de error de la base.
    application.add_exception_handler(SQLAlchemyError, handle_database_error)
    # Fuente única de configuración y motor para dependencias y routers.
    application.state.settings = settings
    # Único punto donde se lee la URL: Settings garantiza que existe tras validarse.
    database_url = cast(SecretStr, settings.database_url).get_secret_value()
    application.state.engine = build_engine(database_url)
    application.state.identity_provider = GoogleIdentityProvider(settings)
    # Agente de cotización (PED-16): None con AI_PROVIDER=fake. Construirlo no abre conexiones.
    api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    application.state.quote_extractor = build_quote_agent(
        provider=cast(Literal["fake", "gemini"], settings.ai_provider),
        api_key=api_key,
        model_name=settings.gemini_model,
        fallback_model_name=settings.gemini_fallback_model,
        timeout_seconds=settings.ai_timeout_seconds,
    )
    # Sesión del dueño en una cookie firmada con SECRET_KEY (research.md R5). Starlette la marca
    # siempre HttpOnly; Secure solo en producción, donde la app se sirve por https.
    application.add_middleware(
        SessionMiddleware,
        secret_key=cast(SecretStr, settings.secret_key).get_secret_value(),
        session_cookie=SESSION_COOKIE,
        max_age=SESSION_MAX_AGE_SECONDS,
        same_site="lax",
        https_only=settings.environment == "production",
    )
    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(catalog.router)
    application.include_router(quotes.router)

    if settings.environment == "production" and settings.ai_provider == "fake":
        logger.warning(
            "Producción usa el proveedor de IA simulado (AI_PROVIDER=fake): "
            "los pedidos no se interpretan con Gemini."
        )
    logger.info(
        "Aplicación iniciada (entorno=%s, commit=%s)", settings.environment, settings.git_commit
    )
    # Los nombres de los modelos no son secretos; la clave nunca se registra.
    logger.info(
        "Cotización con IA: proveedor=%s, modelo=%s, respaldo=%s, tiempo de espera=%s s",
        settings.ai_provider,
        settings.gemini_model,
        settings.gemini_fallback_model or "ninguno",
        settings.ai_timeout_seconds,
    )
    return application


app = create_app()
