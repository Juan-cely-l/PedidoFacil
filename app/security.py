"""Protección de la aplicación: denegar por defecto (research.md R1).

`require_owner` se registra como dependencia de toda la app: cualquier ruta, presente o futura,
exige la sesión del dueño salvo las de `PUBLIC_PATHS`, la única lista de rutas abiertas.
"""

from fastapi import Request

SESSION_COOKIE = "pedidofacil_session"
# Duración máxima de la sesión: una jornada (research.md R5).
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60

# Única lista de rutas abiertas: los health checks (Render) y el propio login.
PUBLIC_PATHS = frozenset(
    {"/health", "/health/live", "/login", "/login/google", "/auth/google/callback"}
)


class LoginRequired(Exception):  # noqa: N818  (nombre del dominio: «hace falta iniciar sesión»)
    """La petición necesita la sesión del dueño; `next_path` es a dónde volver tras entrar."""

    def __init__(self, next_path: str | None) -> None:
        super().__init__(next_path)
        self.next_path = next_path


def require_owner(request: Request) -> None:
    """Dependencia global: deja pasar las rutas públicas y exige el dueño en las demás."""
    raise NotImplementedError
