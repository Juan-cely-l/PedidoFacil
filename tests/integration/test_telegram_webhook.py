"""Webhook del bot de Telegram (specs/005-bot-telegram/spec.md, escenarios 1 a 4).

La Bot API se simula con `httpx2.MockTransport` y la IA con un `FunctionModel`: ninguna prueba
llama a Telegram ni a Gemini (constitución, principio II).
"""

from collections.abc import Iterator

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.routers.quotes import get_quote_extractor
from app.routers.telegram import SECRET_HEADER, WEBHOOK_PATH, get_telegram_bot
from app.services.telegram import TelegramBot
from tests.doubles import EMPTY_EXTRACTION, ScriptedModel, extraction_model, quote_agent

SECRET = "secreto-de-prueba"  # noqa: S105  (valor falso de prueba)
TOKEN = "123456:token-de-prueba"  # noqa: S105  (valor falso de prueba)
CUSTOMER_CHAT = 555


def _update(**message: object) -> dict[str, object]:
    """Una actualización de Telegram con un mensaje privado de un cliente."""
    base: dict[str, object] = {
        "message_id": 1,
        "date": 1_795_000_000,
        "chat": {"id": CUSTOMER_CHAT, "type": "private"},
        "from": {"id": CUSTOMER_CHAT, "is_bot": False, "first_name": "Cliente"},
    }
    return {"update_id": 1000, "message": {**base, **message}}


class BotApi:
    """Bot API simulada: registra cada petición y responde como Telegram."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(200, json={"ok": True, "result": {}})


@pytest.fixture
def bot_api() -> BotApi:
    return BotApi()


@pytest.fixture
def model() -> ScriptedModel:
    return extraction_model(EMPTY_EXTRACTION)


def _app(settings: Settings, bot_api: BotApi, model: ScriptedModel) -> FastAPI:
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    application = create_app(settings)
    bot = TelegramBot(TOKEN, transport=httpx2.MockTransport(bot_api.handle))
    application.dependency_overrides[get_telegram_bot] = lambda: bot
    agent = quote_agent(model)
    application.dependency_overrides[get_quote_extractor] = lambda: agent
    return application


@pytest.fixture
def telegram(
    test_settings: Settings, bot_api: BotApi, model: ScriptedModel
) -> Iterator[TestClient]:
    """Cliente sin sesión (Telegram no la tiene) sobre una app con el bot configurado."""
    settings = Settings(
        _env_file=None,
        environment="test",
        secret_key=test_settings.secret_key,
        telegram_bot_token=SecretStr(TOKEN),
        telegram_webhook_secret=SecretStr(SECRET),
        owner_telegram_chat_id=999,
    )
    with TestClient(_app(settings, bot_api, model)) as client:
        yield client


@pytest.mark.parametrize(
    "headers",
    [pytest.param({}, id="sin_cabecera"), pytest.param({SECRET_HEADER: "otro"}, id="otro_secreto")],
)
def test_sin_el_secreto_correcto_responde_401_y_no_procesa_nada(
    telegram: TestClient,
    bot_api: BotApi,
    model: ScriptedModel,
    headers: dict[str, str],
) -> None:
    response = telegram.post(
        WEBHOOK_PATH, json=_update(text="/catalogo"), headers=headers, follow_redirects=False
    )

    assert response.status_code == 401
    assert bot_api.requests == []
    assert model.calls == 0


def test_con_el_bot_sin_configurar_responde_404(
    test_settings: Settings, bot_api: BotApi, model: ScriptedModel
) -> None:
    with TestClient(_app(test_settings, bot_api, model)) as client:
        response = client.post(
            WEBHOOK_PATH,
            json=_update(text="/catalogo"),
            headers={SECRET_HEADER: SECRET},
            follow_redirects=False,
        )

    # Un 404 propio, no el de una ruta inexistente ({"detail": "Not Found"}).
    assert response.status_code == 404
    assert response.json() == {"detail": "El bot de Telegram no está configurado"}
    assert bot_api.requests == []


@pytest.mark.parametrize(
    "update",
    [
        pytest.param(_update(sticker={"file_id": "x"}), id="sticker"),
        pytest.param(
            {"update_id": 1001, "edited_message": _update(text="otra cosa")["message"]},
            id="mensaje_editado",
        ),
    ],
)
def test_una_actualizacion_sin_texto_responde_200_sin_llamar_a_la_ia(
    telegram: TestClient, model: ScriptedModel, update: dict[str, object]
) -> None:
    response = telegram.post(
        WEBHOOK_PATH, json=update, headers={SECRET_HEADER: SECRET}, follow_redirects=False
    )

    assert response.status_code == 200
    assert model.calls == 0
