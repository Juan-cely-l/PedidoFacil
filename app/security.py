"""Protección de la aplicación: denegar por defecto (research.md R1).

`require_owner` se registra como dependencia de toda la app: cualquier ruta, presente o futura,
exige la sesión del dueño salvo las de `PUBLIC_PATHS`, la única lista de rutas abiertas.
"""

import time
from urllib.parse import urlencode

from fastapi import Request, status
from fastapi.responses import RedirectResponse

from app.config import Settings
from app.services.auth import SESSION_MAX_AGE_SECONDS, current_owner

__all__ = [
    "PUBLIC_PATHS",
    "SESSION_COOKIE",
    "SESSION_MAX_AGE_SECONDS",
    "LoginRequired",
    "redirect_to_login",
    "require_owner",
]

SESSION_COOKIE = "pedidofacil_session"

# Única lista de rutas abiertas: los health checks (Render) y el propio login.
PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/health/live",
        "/login",
        "/login/google",
        "/auth/google/callback",
        # Telegram no tiene sesión: el webhook lo protege su token secreto (principio VI).
        "/telegram/webhook",
    }
)


class LoginRequired(Exception):  # noqa: N818  (nombre del dominio: «hace falta iniciar sesión»)
    """La petición necesita la sesión del dueño; `next_path` es a dónde volver tras entrar."""

    def __init__(self, next_path: str | None) -> None:
        super().__init__(next_path)
        self.next_path = next_path


def require_owner(request: Request) -> None:
    """Dependencia global: deja pasar las rutas públicas y exige el dueño en las demás.

    Sin dueño válido vacía la sesión y lanza LoginRequired. Solo las peticiones GET recuerdan
    a dónde volver: un formulario enviado no se puede repetir con una redirección.
    """
    if request.url.path in PUBLIC_PATHS:
        return
    settings: Settings = request.app.state.settings
    owner = current_owner(request.session, settings.owner_emails, time.time())
    if owner is None:
        request.session.clear()
        next_path = None
        if request.method == "GET":
            query = request.url.query
            next_path = request.url.path + (f"?{query}" if query else "")
        raise LoginRequired(next_path)
    request.state.owner = owner


async def redirect_to_login(request: Request, exc: Exception) -> RedirectResponse:  # noqa: ARG001
    """Manejador de LoginRequired: 303 al login, con el destino si lo hay."""
    next_path = exc.next_path if isinstance(exc, LoginRequired) else None
    url = "/login" if next_path is None else "/login?" + urlencode({"next": next_path})
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
