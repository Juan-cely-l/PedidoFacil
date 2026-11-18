"""Acceso del dueño con Google (contracts/auth-routes.md).

`/login`, `/login/google` y `/auth/google/callback` son públicas. La sesión guarda solo al
dueño: nunca tokens (constitución VI).
"""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.config import Settings, get_app_settings
from app.services.auth import DEFAULT_AFTER_LOGIN, safe_next_path, start_session
from app.services.identity import IdentityProvider, get_identity_provider
from app.templating import templates

logger = logging.getLogger("pedidofacil.auth")

router = APIRouter(tags=["acceso"])

AppSettings = Annotated[Settings, Depends(get_app_settings)]
Provider = Annotated[IdentityProvider, Depends(get_identity_provider)]
NextPath = Annotated[str | None, Query(alias="next")]

# Avisos de la página de login: solo códigos conocidos, nunca texto que venga en la URL (R11).
NOTICES = {"error": "No se pudo iniciar sesión con Google. Intenta de nuevo"}


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next_path: NextPath = None, aviso: str | None = None) -> Response:
    """Página de login; con sesión, lleva directo al destino o al catálogo."""
    if request.session.get("owner"):
        return _redirect(safe_next_path(next_path) or DEFAULT_AFTER_LOGIN)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"login_url": "/login/google", "notice": NOTICES.get(aviso or "")},
    )


@router.get("/login/google")
async def login_with_google(
    request: Request, settings: AppSettings, provider: Provider, next_path: NextPath = None
) -> Response:
    """Envía al dueño a Google; recuerda el destino ya validado."""
    if settings.google_client_id is None or settings.google_client_secret is None:
        # Solo posible fuera de producción, que no arranca sin estas variables.
        logger.warning("Login con Google sin configurar (faltan GOOGLE_CLIENT_ID o el secreto)")
        return _redirect("/login?aviso=error")
    request.session["login_next"] = safe_next_path(next_path)
    return await provider.start_login(request, settings.oauth_redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(request: Request, provider: Provider) -> Response:
    """Vuelta desde Google: abre la sesión del dueño y lo lleva a donde quería ir."""
    identity = await provider.complete_login(request)
    destination = safe_next_path(request.session.get("login_next"))
    start_session(request.session, identity, time.time())
    logger.info("Inicio de sesión aceptado")
    return _redirect(destination or DEFAULT_AFTER_LOGIN)
