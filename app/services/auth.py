"""Reglas del acceso del dueño: correos, destino de retorno y sesión.

Módulo puro: no importa la configuración ni hace HTTP, para probarlo con pruebas unitarias.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.identity import VerifiedIdentity


def normalize_email(email: str) -> str:
    """Correo para comparar: sin espacios al inicio ni al final y sin distinguir mayúsculas."""
    return email.strip().casefold()


def safe_next_path(raw: str | None) -> str | None:
    """Destino de retorno tras el login, solo si es un path propio; si no, None."""
    raise NotImplementedError


def start_session(session: dict[str, Any], identity: "VerifiedIdentity", now: float) -> None:
    """Vacía la sesión y guarda solo al dueño (correo, nombre y momento del login)."""
    raise NotImplementedError
