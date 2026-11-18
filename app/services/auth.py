"""Reglas del acceso del dueño: correos, destino de retorno y sesión.

Módulo puro: no importa la configuración ni hace HTTP, para probarlo con pruebas unitarias.
"""

from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from app.services.identity import VerifiedIdentity

DEFAULT_AFTER_LOGIN = "/productos"
# Volver a una ruta del propio login tras entrar no tiene sentido y puede crear bucles.
_LOGIN_PATHS = frozenset({"/login", "/login/google", "/auth/google/callback", "/logout"})


def normalize_email(email: str) -> str:
    """Correo para comparar: sin espacios al inicio ni al final y sin distinguir mayúsculas."""
    return email.strip().casefold()


def safe_next_path(raw: str | None) -> str | None:
    """Destino de retorno tras el login, solo si es un path propio; si no, None.

    Rechaza todo lo que el navegador podría tratar como URL absoluta: «//host» y cualquier
    barra invertida («/\\host» se normaliza a «//host»), además de esquemas y caracteres de
    control (research.md R4).
    """
    if not raw or not raw.startswith("/") or raw.startswith("//") or "\\" in raw:
        return None
    if not raw.isprintable():  # saltos de línea, tabuladores y otros caracteres de control
        return None
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or parts.path in _LOGIN_PATHS:
        return None
    return raw


def start_session(session: dict[str, Any], identity: "VerifiedIdentity", now: float) -> None:
    """Vacía la sesión y guarda solo al dueño (correo, nombre y momento del login).

    Limpiar primero evita que sobreviva nada de antes del login: ni datos de un tercero
    (fijación de sesión) ni el estado temporal de OAuth, que authlib guarda en la sesión.
    """
    session.clear()
    session["owner"] = {
        "email": normalize_email(identity.email),
        "name": identity.name,
        "login_at": now,
    }
