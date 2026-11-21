"""Dobles de prueba compartidos."""

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any, NoReturn

import httpx2  # el cliente HTTP de TestClient (llega con fastapi[standard])
from fastapi import Request
from fastapi.testclient import TestClient
from itsdangerous import BadSignature, TimestampSigner
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy.exc import OperationalError
from sqlmodel import Session
from starlette.responses import RedirectResponse, Response

from app.services.identity import LoginFailed, VerifiedIdentity
from tests.banco_mensajes import CasoBanco

# Mensaje con credenciales, como el que daría el controlador real: nunca debe filtrarse.
LEAKY_DB_ERROR = "no se pudo conectar a postgresql://usuario:clave@host/db"


class FailingSession(Session):
    """Sesión que simula una base de datos caída: toda consulta lanza OperationalError."""

    def exec(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise OperationalError("SELECT 1", {}, Exception(LEAKY_DB_ERROR))

    def execute(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise OperationalError("SELECT 1", {}, Exception(LEAKY_DB_ERROR))


# Acceso del dueño (PED-15)

SESSION_COOKIE = "pedidofacil_session"
# Los tokens falsos empiezan así: ninguna prueba debe encontrarlos en logs, respuestas o sesión.
TOKEN_SENTINEL = "TOKEN-CENTINELA-"  # noqa: S105  (valor falso reconocible)
OWNER = VerifiedIdentity(email="dueno@example.com", email_verified=True, name="Dueño")


class FakeIdentityProvider:
    """Proveedor de identidad simulado: nunca habla con Google.

    `start_login` deja en la sesión datos temporales con un token centinela, como hace authlib
    con su state; `start_session` debe borrarlos al entrar.
    """

    def __init__(self) -> None:
        self.identity: VerifiedIdentity = OWNER
        self.failure: LoginFailed | None = None

    async def start_login(self, request: Request, redirect_uri: str) -> Response:
        request.session["_state_google_falso"] = {"data": {"hint": f"{TOKEN_SENTINEL}STATE"}}
        return RedirectResponse(f"{redirect_uri}?state=falso&code=falso", status_code=302)

    async def complete_login(self, request: Request) -> VerifiedIdentity:  # noqa: ARG002
        if self.failure is not None:
            raise self.failure
        return self.identity


class ExplodingIdentityProvider:
    """Falla la prueba si alguien intenta usar el proveedor (debe no contactarse con Google)."""

    async def start_login(self, request: Request, redirect_uri: str) -> Response:  # noqa: ARG002
        raise AssertionError("no debía iniciarse el login con Google")

    async def complete_login(self, request: Request) -> VerifiedIdentity:  # noqa: ARG002
        raise AssertionError("no debía completarse el login con Google")


def read_session(client: TestClient, secret_key: str) -> dict[str, Any]:
    """Decodifica la cookie de sesión como lo hace Starlette (firma + base64 + JSON)."""
    cookie = client.cookies.get(SESSION_COOKIE)
    if not cookie:
        return {}
    try:
        data = TimestampSigner(secret_key).unsign(cookie.encode())
    except BadSignature:
        return {}
    decoded: dict[str, Any] = json.loads(base64.b64decode(data))
    return decoded


def log_in(client: TestClient, next_path: str | None = None) -> httpx2.Response:
    """Recorre /login/google → callback con el proveedor que tenga la app y devuelve la
    respuesta del callback (sin seguir su redirección)."""
    params = {"next": next_path} if next_path is not None else None
    start = client.get("/login/google", params=params, follow_redirects=False)
    assert start.status_code == 302, start.text
    return client.get(start.headers["location"], follow_redirects=False)


# Cotización con IA (PED-16): modelos simulados. Ninguno llama a Gemini (constitución II).

ModelFunction = Callable[[list[ModelMessage], AgentInfo], Awaitable[ModelResponse]]

EMPTY_EXTRACTION: dict[str, object] = {
    "lines": [],
    "delivery_date": None,
    "delivery_time": None,
    "delivery_mode": None,
    "delivery_address": None,
}


class ScriptedModel(FunctionModel):
    """`FunctionModel` que cuenta sus llamadas en `calls`.

    Las pruebas de validación lo usan para comprobar que la IA no se consultó (`calls == 0`).
    """

    def __init__(self, function: ModelFunction, *, model_name: str = "modelo-falso") -> None:
        self.calls = 0

        async def counted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            self.calls += 1
            return await function(messages, info)

        super().__init__(counted, model_name=model_name)


def _output_call(info: AgentInfo, payload: dict[str, object]) -> ModelResponse:
    """Respuesta que entrega `payload` como salida estructurada del agente."""
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, payload)])


def extraction_model(payload: dict[str, object]) -> ScriptedModel:
    """Modelo que responde siempre con `payload` como extracción (válida o no)."""

    async def respond(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return _output_call(info, payload)

    return ScriptedModel(respond)


def slow_model(seconds: float) -> ScriptedModel:
    """Modelo que tarda `seconds` antes de responder una extracción vacía."""

    async def respond(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(seconds)
        return _output_call(info, EMPTY_EXTRACTION)

    return ScriptedModel(respond)


def failing_model(status_code: int = 503) -> ScriptedModel:
    """Modelo que responde con un error HTTP del proveedor (saturación, cuota…)."""

    async def respond(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(status_code, "modelo-falso")

    return ScriptedModel(respond)


def extraction_from_bank(caso: CasoBanco) -> dict[str, object]:
    """La extracción que daría una IA perfecta para un caso del banco (research R14).

    Los no reconocidos van con `product_id=None`; el mensaje que no es un pedido, sin líneas.
    Nunca lleva precios: el banco no los tiene.
    """
    lines = [
        {
            "customer_text": caso.texto[:200],
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "quantity": item.quantity,
        }
        for item in caso.esperado
    ]
    return {**EMPTY_EXTRACTION, "lines": lines}
