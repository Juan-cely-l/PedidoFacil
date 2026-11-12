"""Health checks: /health/live para la plataforma y /health para el job de despliegue."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app import __version__
from app.config import Settings, get_app_settings
from app.db import get_session
from app.services.health import check_database

router = APIRouter(tags=["operación"])

AppSettings = Annotated[Settings, Depends(get_app_settings)]


@router.get("/health/live")
def live(settings: AppSettings) -> dict[str, str]:
    """El proceso está vivo. No consulta la base: Render lo llama con frecuencia."""
    return {"status": "ok", "version": __version__, "commit": settings.short_commit}


@router.get(
    "/health",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "La base no responde"}},
)
def health(
    settings: AppSettings, session: Annotated[Session, Depends(get_session)]
) -> JSONResponse:
    """La aplicación y su base de datos responden; lo consulta el job de despliegue."""
    healthy = check_database(session)
    state = "ok" if healthy else "error"
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": state,
            "database": state,
            "version": __version__,
            "commit": settings.short_commit,
        },
    )
