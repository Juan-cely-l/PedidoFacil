"""Proveedor de identidad del dueño: Google OAuth 2.0 / OpenID Connect (ADR 0003).

`IdentityProvider` es la interfaz que usan los routers; `GoogleIdentityProvider` la implementa
con authlib y es el único módulo que habla con Google. Las pruebas la sustituyen con
`app.dependency_overrides[get_identity_provider]` o le inyectan un `httpx2.MockTransport`
(authlib usa httpx2, no httpx).
"""

from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx2

# authlib no publica tipos (sin py.typed): su uso queda aislado en este módulo.
from authlib.integrations.starlette_client import OAuth  # type: ignore[import-untyped]
from fastapi import Request
from starlette.responses import Response

from app.config import Settings

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
# openid activa OpenID Connect: authlib genera y valida el nonce del id_token (research.md R7).
GOOGLE_SCOPE = "openid email profile"


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
        client_kwargs: dict[str, Any] = {"scope": GOOGLE_SCOPE}
        if transport is not None:
            # Solo las pruebas lo pasan: un Google simulado, sin red.
            client_kwargs["transport"] = transport
        secret = settings.google_client_secret
        oauth = OAuth()
        oauth.register(
            "google",
            client_id=settings.google_client_id,
            client_secret=secret.get_secret_value() if secret is not None else None,
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs=client_kwargs,
        )
        self._client = oauth.create_client("google")

    async def start_login(self, request: Request, redirect_uri: str) -> Response:
        """Redirige a Google; authlib guarda state y nonce en la sesión."""
        return cast(Response, await self._client.authorize_redirect(request, redirect_uri))

    async def complete_login(self, request: Request) -> VerifiedIdentity:
        """Valida state, id_token (firma, emisor, destinatario, expiración) y nonce."""
        token = await self._client.authorize_access_token(request)
        userinfo = token["userinfo"]
        email = str(userinfo.get("email") or "")
        return VerifiedIdentity(
            email=email,
            email_verified=userinfo.get("email_verified") is True,
            name=str(userinfo.get("name") or email),
        )


def get_identity_provider(request: Request) -> IdentityProvider:
    """Dependencia de FastAPI: el proveedor que creó la app (sustituible en las pruebas)."""
    return cast(IdentityProvider, request.app.state.identity_provider)
