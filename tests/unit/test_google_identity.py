"""GoogleIdentityProvider con authlib real contra un Google simulado (research.md R7).

authlib 1.9 usa httpx2 (no httpx): el Google simulado es un `httpx2.MockTransport` que responde
los metadatos de OpenID, las claves públicas (JWKS) y el endpoint de token. Ninguna petición sale
a la red (constitución II). El id_token se firma con una clave RSA generada en la prueba con
joserfc, la biblioteca JOSE que trae authlib.
"""

import asyncio
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
from joserfc import jwt
from joserfc.jwk import RSAKey
from starlette.requests import Request

from app.config import Settings
from app.services.identity import GoogleIdentityProvider, VerifiedIdentity

CLIENT_ID = "test-client-id"  # el de la fixture test_settings
REDIRECT_URI = "http://testserver/auth/google/callback"
ISSUER = "https://accounts.google.com"
METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105  (es una URL, no un secreto)
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
ACCESS_TOKEN = "TOKEN-CENTINELA-ACCESO"  # noqa: S105  (valor falso reconocible)
AUTH_CODE = "CODIGO-CENTINELA"
KEY_ID = "clave-de-prueba"


class FakeGoogle:
    """Google simulado: metadatos OIDC, JWKS y endpoint de token con un id_token firmado."""

    def __init__(self) -> None:
        self.key = RSAKey.generate_key(2048, parameters={"kid": KEY_ID})
        self.nonce: str | None = None
        self.requests: list[httpx2.Request] = []

    def id_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "1234567890",
            "iat": now,
            "exp": now + 3600,
            "email": "dueno@example.com",
            "email_verified": True,
            "name": "Dueño",
            "nonce": self.nonce,
        }
        return jwt.encode({"alg": "RS256", "kid": KEY_ID}, claims, self.key)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        url = str(request.url).split("?", 1)[0]
        if url == METADATA_URL:
            return httpx2.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": AUTHORIZATION_ENDPOINT,
                    "token_endpoint": TOKEN_ENDPOINT,
                    "jwks_uri": JWKS_URI,
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if url == JWKS_URI:
            return httpx2.Response(200, json={"keys": [self.key.as_dict(private=False)]})
        if url == TOKEN_ENDPOINT:
            return httpx2.Response(
                200,
                json={
                    "access_token": ACCESS_TOKEN,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "id_token": self.id_token(),
                },
            )
        return httpx2.Response(404)


def make_request(session: dict[str, Any], query: str = "") -> Request:
    """Petición de Starlette con sesión, como la que recibe el router tras SessionMiddleware."""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/google/callback",
            "query_string": query.encode(),
            "headers": [],
            "session": session,
        }
    )


def make_provider(settings: Settings, google: FakeGoogle) -> GoogleIdentityProvider:
    return GoogleIdentityProvider(settings, transport=httpx2.MockTransport(google.handle))


def start_login(provider: GoogleIdentityProvider, session: dict[str, Any]) -> dict[str, str]:
    """Ida a Google: devuelve los parámetros de la URL de autorización."""
    response = asyncio.run(provider.start_login(make_request(session), REDIRECT_URI))
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(AUTHORIZATION_ENDPOINT)
    return {name: values[0] for name, values in parse_qs(urlsplit(location).query).items()}


# Historia 1: un inicio de sesión válido (T011)


def test_iniciar_redirige_a_google_con_state_y_nonce_guardados_en_la_sesion(
    test_settings: Settings,
) -> None:
    provider = make_provider(test_settings, FakeGoogle())
    session: dict[str, Any] = {}

    params = start_login(provider, session)

    assert params["client_id"] == CLIENT_ID
    assert params["redirect_uri"] == REDIRECT_URI
    assert params["response_type"] == "code"
    assert set(params["scope"].split()) == {"openid", "email", "profile"}
    assert params["state"]
    assert params["nonce"]
    assert f"_state_google_{params['state']}" in session


def test_una_vuelta_valida_de_google_devuelve_la_identidad_verificada(
    test_settings: Settings,
) -> None:
    google = FakeGoogle()
    provider = make_provider(test_settings, google)
    session: dict[str, Any] = {}
    params = start_login(provider, session)
    google.nonce = params["nonce"]

    callback = make_request(session, f"code={AUTH_CODE}&state={params['state']}")
    identity = asyncio.run(provider.complete_login(callback))

    assert identity == VerifiedIdentity(
        email="dueno@example.com", email_verified=True, name="Dueño"
    )
    token_requests = [r for r in google.requests if str(r.url) == TOKEN_ENDPOINT]
    assert len(token_requests) == 1
    assert AUTH_CODE in token_requests[0].content.decode()
