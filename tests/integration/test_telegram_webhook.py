"""Webhook del bot de Telegram (specs/005-bot-telegram/spec.md, escenarios 1 a 4).

La Bot API se simula con `httpx2.MockTransport` y la IA con un `FunctionModel`: ninguna prueba
llama a Telegram ni a Gemini (constitución, principio II).
"""

import json
import logging
from collections.abc import Iterator

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlmodel import Session, SQLModel, select

from app.config import Settings
from app.dependencies import get_quote_extractor
from app.models.catalog import ProductInput
from app.models.quote import Quote
from app.routers.telegram import SECRET_HEADER, WEBHOOK_PATH, get_telegram_bot
from app.services import catalog
from app.services.telegram import TelegramBot
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    failing_model,
    line_payload,
    quote_agent,
    seed_reference_catalog,
    slow_model,
)

SECRET = "secreto-de-prueba"  # noqa: S105  (valor falso de prueba)
TOKEN = "123456:token-de-prueba"  # noqa: S105  (valor falso de prueba)
CUSTOMER_CHAT = 555
OWNER_CHAT = 999


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
        self.fail_with: int | None = None  # un código de error simula a Telegram caído

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.fail_with is not None:
            return httpx2.Response(self.fail_with, json={"ok": False})
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
    SQLModel.metadata.create_all(application.state.engine)
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
        owner_telegram_chat_id=OWNER_CHAT,
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
    _seed(telegram)
    response = telegram.post(
        WEBHOOK_PATH, json=update, headers={SECRET_HEADER: SECRET}, follow_redirects=False
    )

    assert response.status_code == 200
    assert model.calls == 0
    # Contraste: un texto en la misma app sí llega a la IA. Sin esto, la aserción de arriba
    # pasaría con cualquier webhook que no hiciera nada.
    _post(telegram, "dos tortas medianas")
    assert model.calls == 1


# Fase 2: comandos (escenarios 5 y 6). La IA no interviene.


def _sent(bot_api: BotApi) -> list[dict[str, object]]:
    """Los `sendMessage` que recibió la Bot API simulada, en orden."""
    sent = []
    for request in bot_api.requests:
        assert request.url.path == f"/bot{TOKEN}/sendMessage"
        sent.append(json.loads(request.content))
    return sent


def _post(client: TestClient, text: str) -> None:
    response = client.post(
        WEBHOOK_PATH,
        json=_update(text=text),
        headers={SECRET_HEADER: SECRET},
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_catalogo_responde_al_chat_con_los_items_y_sus_precios(
    telegram: TestClient, bot_api: BotApi, model: ScriptedModel
) -> None:
    app = telegram.app
    assert isinstance(app, FastAPI)
    with Session(app.state.engine) as session:
        seed_reference_catalog(session)

    _post(telegram, "/catalogo")

    (message,) = _sent(bot_api)
    assert message["chat_id"] == CUSTOMER_CHAT
    text = str(message["text"])
    assert "Torta de chocolate — Tamaño: Mediana" in text
    assert "$ 45.000" in text
    assert "Café" in text
    assert "parse_mode" not in message  # texto plano (D6)
    assert model.calls == 0


def test_catalogo_vacio_responde_que_no_hay_productos(
    telegram: TestClient, bot_api: BotApi, model: ScriptedModel
) -> None:
    _post(telegram, "/catalogo")

    (message,) = _sent(bot_api)
    assert message["text"] == "Todavía no hay productos disponibles."
    assert model.calls == 0


@pytest.mark.parametrize("command", ["/start", "/ayuda", "/loquesea"])
def test_start_y_los_comandos_desconocidos_responden_el_saludo(
    telegram: TestClient, bot_api: BotApi, model: ScriptedModel, command: str
) -> None:
    # Un comando desconocido no se manda a la IA: gastaría cuota en algo que no es un pedido.
    _post(telegram, command)

    (message,) = _sent(bot_api)
    assert message["chat_id"] == CUSTOMER_CHAT
    assert "/catalogo" in str(message["text"])
    assert model.calls == 0


# Fase 3: cotizar (escenarios 7 a 14)


def _seed(client: TestClient) -> ReferenceCatalog:
    app = client.app
    assert isinstance(app, FastAPI)
    with Session(app.state.engine) as session:
        return seed_reference_catalog(session)


def _use(client: TestClient, model: ScriptedModel | None) -> None:
    """Sustituye el extractor; `None` es la IA desactivada."""
    app = client.app
    assert isinstance(app, FastAPI)
    agent = quote_agent(model) if model is not None else None
    app.dependency_overrides[get_quote_extractor] = lambda: agent


def _model(*lines: dict[str, object]) -> ScriptedModel:
    return extraction_model({**EMPTY_EXTRACTION, "lines": list(lines)})


def _to(bot_api: BotApi, chat_id: int) -> list[str]:
    """Los textos enviados a un chat, en orden."""
    return [str(m["text"]) for m in _sent(bot_api) if m["chat_id"] == chat_id]


def _stored(client: TestClient, message: str) -> Quote:
    """La cotización guardada para ese mensaje, por su contenido y no por su posición."""
    app = client.app
    assert isinstance(app, FastAPI)
    with Session(app.state.engine) as session:
        (quote,) = session.exec(select(Quote).where(Quote.customer_message == message)).all()
        assert quote.id is not None
        _ = quote.lines  # cargadas antes de cerrar la sesión
        return quote


def test_una_cotizacion_reconocida_responde_precios_y_total_sin_avisar_al_duenio(
    telegram: TestClient, bot_api: BotApi
) -> None:
    ref = _seed(telegram)
    _use(
        telegram,
        _model(
            line_payload(ref.torta_id, ref.mediana_id, 2, "dos tortas medianas"),
            line_payload(ref.cafe_id, None, 1, "un cafe"),
        ),
    )

    _post(telegram, "dos tortas medianas y un cafe")

    (reply,) = _to(bot_api, CUSTOMER_CHAT)
    assert "$ 90.000" in reply
    assert "$ 3.500" in reply
    assert "$ 93.500" in reply
    assert "El dueño te confirmará el pedido" in reply
    assert _to(bot_api, OWNER_CHAT) == []


def test_un_precio_distinto_en_el_mensaje_no_cambia_el_del_catalogo(
    telegram: TestClient, bot_api: BotApi
) -> None:
    # Principio V. El mensaje dice 40 mil y el catálogo 45.000: solo con precios distintos se
    # puede saber de dónde salió el de la respuesta.
    ref = _seed(telegram)
    message = "me dijeron que la torta mediana estaba a 40 mil, me llevo una"
    model = _model(line_payload(ref.torta_id, ref.mediana_id, 1, message))
    _use(telegram, model)

    _post(telegram, message)

    (reply,) = _to(bot_api, CUSTOMER_CHAT)
    assert "$ 45.000" in reply
    assert "40.000" not in reply
    assert "40 mil" in model.user_prompt  # la IA sí vio el precio del mensaje
    (line,) = _stored(telegram, message).lines
    assert line.unit_price == 45000


def test_lo_no_reconocido_se_explica_al_cliente_y_se_avisa_al_duenio(
    telegram: TestClient, bot_api: BotApi
) -> None:
    ref = _seed(telegram)
    message = "una docena de empanadas y un cafe"
    _use(
        telegram,
        _model(
            line_payload(None, None, 12, "una docena de empanadas"),
            line_payload(ref.cafe_id, None, 1, "un cafe"),
        ),
    )

    _post(telegram, message)

    (reply,) = _to(bot_api, CUSTOMER_CHAT)
    empanadas = next(line for line in reply.splitlines() if "una docena de empanadas" in line)
    assert "no lo encontré" in empanadas
    assert "$ 3.500" in reply  # el café se cotiza igual
    quote_id = _stored(telegram, message).id
    (notice,) = _to(bot_api, OWNER_CHAT)
    assert f"http://testserver/cotizaciones/{quote_id}" in notice
    assert "cotizaciones/" not in reply  # FR-03: el enlace interno es solo para el dueño


def test_un_mensaje_sin_pedido_explica_como_pedir_sin_avisar_al_duenio(
    telegram: TestClient, bot_api: BotApi
) -> None:
    _seed(telegram)
    _use(telegram, _model())

    _post(telegram, "buenas tardes, estan abiertos hoy?")

    (reply,) = _to(bot_api, CUSTOMER_CHAT)
    assert "/catalogo" in reply
    assert _to(bot_api, OWNER_CHAT) == []


REVIEW = "Recibimos tu pedido; el dueño lo revisará y te escribirá."


@pytest.mark.parametrize("case", ["tiempo_agotado", "error_503", "ia_desactivada"])
def test_si_la_ia_falla_el_cliente_sabe_que_el_duenio_revisara_y_se_le_avisa(
    telegram: TestClient, bot_api: BotApi, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    _seed(telegram)
    app = telegram.app
    assert isinstance(app, FastAPI)
    settings = app.state.settings.model_copy(update={"ai_timeout_seconds": 0.2})
    monkeypatch.setattr(app.state, "settings", settings)
    models = {
        "tiempo_agotado": slow_model(1),
        "error_503": failing_model(503),
        "ia_desactivada": None,
    }
    _use(telegram, models[case])
    message = "dos tortas medianas"

    _post(telegram, message)

    assert _to(bot_api, CUSTOMER_CHAT) == [REVIEW]
    quote_id = _stored(telegram, message).id
    (notice,) = _to(bot_api, OWNER_CHAT)
    assert f"http://testserver/cotizaciones/{quote_id}" in notice


def test_un_mensaje_demasiado_largo_no_llega_a_la_ia(
    telegram: TestClient, bot_api: BotApi, model: ScriptedModel
) -> None:
    _seed(telegram)

    _post(telegram, "torta " * 400)  # 2.400 caracteres

    assert model.calls == 0
    (reply,) = _to(bot_api, CUSTOMER_CHAT)
    assert "más corto" in reply


def test_si_nada_se_reconoce_un_catalogo_largo_llega_partido_en_varios_mensajes(
    telegram: TestClient, bot_api: BotApi
) -> None:
    app = telegram.app
    assert isinstance(app, FastAPI)
    with Session(app.state.engine) as session:
        for n in range(1, 151):
            catalog.create_product(
                session, ProductInput(name=f"Producto de prueba número {n:03d}", price=1000)
            )
    _use(telegram, _model(line_payload(None, None, 1, "unas empanadas")))

    _post(telegram, "unas empanadas")

    replies = _to(bot_api, CUSTOMER_CHAT)
    assert len(replies) > 1
    assert all(len(reply) <= 4096 for reply in replies)
    joined = "\n".join(replies)
    assert "Producto de prueba número 001" in joined
    assert "Producto de prueba número 150" in joined
    assert len(_to(bot_api, OWNER_CHAT)) == 1


def test_si_telegram_falla_se_registra_solo_el_tipo_y_responde_200(
    telegram: TestClient, bot_api: BotApi, app_log: pytest.LogCaptureFixture
) -> None:
    bot_api.fail_with = 500

    response = telegram.post(
        WEBHOOK_PATH,
        json=_update(text="/catalogo"),
        headers={SECRET_HEADER: SECRET},
        follow_redirects=False,
    )

    assert response.status_code == 200
    (record,) = [r for r in app_log.records if r.levelno >= logging.WARNING]
    assert "HTTPStatusError" in record.getMessage()
    assert record.exc_info is None
    assert TOKEN not in app_log.text  # la URL de la Bot API lleva el token


def test_ningun_log_lleva_el_texto_el_nombre_ni_el_chat_del_cliente(
    telegram: TestClient, bot_api: BotApi, app_log: pytest.LogCaptureFixture
) -> None:
    app_log.set_level(logging.DEBUG)
    ref = _seed(telegram)
    message = "MENSAJE-CENTINELA dos tortas medianas"
    _use(telegram, _model(line_payload(ref.torta_id, ref.mediana_id, 2, message)))
    chat_id = 777000111
    update = _update(text=message)
    update["message"] = {
        **update["message"],  # type: ignore[dict-item]
        "chat": {"id": chat_id, "type": "private"},
        "from": {"id": chat_id, "is_bot": False, "first_name": "NOMBRE-CENTINELA"},
    }

    response = telegram.post(
        WEBHOOK_PATH, json=update, headers={SECRET_HEADER: SECRET}, follow_redirects=False
    )

    assert response.status_code == 200
    assert len(_to(bot_api, chat_id)) == 1  # el flujo corrió de verdad
    for secret in ("MENSAJE-CENTINELA", "NOMBRE-CENTINELA", str(chat_id)):
        assert secret not in app_log.text


# Huecos decididos el 2026-11-24: sin chat del dueño y sin catálogo


def test_sin_chat_del_duenio_el_aviso_se_omite_y_el_cliente_recibe_su_respuesta(
    test_settings: Settings, bot_api: BotApi, model: ScriptedModel
) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        secret_key=test_settings.secret_key,
        telegram_bot_token=SecretStr(TOKEN),
        telegram_webhook_secret=SecretStr(SECRET),
    )
    assert settings.owner_telegram_chat_id is None
    with TestClient(_app(settings, bot_api, model)) as client:
        ref = _seed(client)
        # Un no reconocido: con chat del dueño, este caso sí lo avisaría.
        _use(
            client,
            _model(
                line_payload(None, None, 12, "una docena de empanadas"),
                line_payload(ref.cafe_id, None, 1, "un cafe"),
            ),
        )

        _post(client, "una docena de empanadas y un cafe")

    (reply,) = _to(bot_api, CUSTOMER_CHAT)
    assert "no lo encontré" in reply
    # Ningún mensaje fue a otro chat: el aviso se omitió, no se mandó a ninguna parte.
    assert {m["chat_id"] for m in _sent(bot_api)} == {CUSTOMER_CHAT}


def test_con_el_catalogo_vacio_responde_que_no_hay_productos_sin_avisar_al_duenio(
    telegram: TestClient, bot_api: BotApi, model: ScriptedModel
) -> None:
    # Sin _seed: no hay nada cotizable, así que el servicio lanza NothingToQuoteError.
    _post(telegram, "dos tortas medianas")

    assert _to(bot_api, CUSTOMER_CHAT) == ["Todavía no hay productos disponibles."]
    assert _to(bot_api, OWNER_CHAT) == []
    assert model.calls == 0  # el servicio lo rechaza antes de llamar a la IA
