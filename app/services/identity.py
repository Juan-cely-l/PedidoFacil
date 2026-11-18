"""Proveedor de identidad del dueño: Google OAuth 2.0 / OpenID Connect (ADR 0003).

`IdentityProvider` es la interfaz que usan los routers; `GoogleIdentityProvider` la implementa
con authlib y es el único módulo que habla con Google. Las pruebas la sustituyen con
`app.dependency_overrides[get_identity_provider]` o le inyectan un `httpx2.MockTransport`
(authlib usa httpx2, no httpx).
"""

from dataclasses import dataclass
from typing import Protocol

import httpx2
from fastapi import Request
from starlette.responses import Response

from app.config import Settings


@dataclass(frozen=True)
class VerifiedIdentity:
    """Lo que se sabe del dueño tras validar el id_token: nunca incluye tokens."""

    email: str
    email_verified: bool
    name: str


class LoginFailed(Exception):  # noqa: N818  (nombre del dominio: «el inicio de sesión falló»)
    """El inicio de sesión no se completó; `reason` es un código corto, sin datos sensibles."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class IdentityProvider(Protocol):
    """Interfaz del proveedor de identidad."""

    async def start_login(self, request: Request, redirect_uri: str) -> Response:
        """Redirige al proveedor para que el dueño se identifique."""
        ...

    async def complete_login(self, request: Request) -> VerifiedIdentity:
        """Valida la vuelta del proveedor y devuelve la identidad, o lanza LoginFailed."""
        ...


class GoogleIdentityProvider:
    """Implementación con authlib contra Google."""

    def __init__(
        self, settings: Settings, transport: httpx2.AsyncBaseTransport | None = None
    ) -> None:
        raise NotImplementedError

    async def start_login(self, request: Request, redirect_uri: str) -> Response:
        """Redirige a Google con state y nonce guardados en la sesión."""
        raise NotImplementedError

    async def complete_login(self, request: Request) -> VerifiedIdentity:
        """Valida state, id_token y nonce, y devuelve la identidad."""
        raise NotImplementedError


def get_identity_provider(request: Request) -> IdentityProvider:
    """Dependencia de FastAPI: el proveedor que creó la app."""
    raise NotImplementedError
