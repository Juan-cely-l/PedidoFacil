"""Errores de la base de datos que llegan al borde de la app (FR-018, research R11)."""

import logging

from fastapi import Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import StatementError

from app.templating import templates

logger = logging.getLogger("pedidofacil.db")


async def handle_database_error(request: Request, exc: Exception) -> HTMLResponse:
    """Manejador de SQLAlchemyError (como un `@ExceptionHandler` de Spring), igual en todo ambiente.

    Registra los tipos y la ruta. Nunca `str(exc)` ni la traza: PostgreSQL agrega un `DETAIL` con
    la fila entera, que trae el mensaje y la dirección del cliente aunque `hide_parameters` oculte
    los parámetros.
    """
    driver_error = exc.orig if isinstance(exc, StatementError) else None
    logger.error(
        "Error de la base de datos: error=%s origen=%s ruta=%s %s",
        type(exc).__name__,
        _qualified_name(driver_error) if driver_error is not None else "ninguno",
        request.method,
        request.url.path,  # sin la consulta de la URL
    )
    return templates.TemplateResponse(
        request, "errors/database.html", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def _qualified_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"
