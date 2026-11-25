"""Cliente de la Bot API (app/services/telegram.py), con `httpx2.MockTransport`: sin red."""

import asyncio
import json
import logging

import httpx2
import pytest

from app.services.telegram import TelegramBot

TOKEN = "123456:token-de-prueba"  # noqa: S105  (valor falso de prueba)


def test_send_message_hace_un_post_a_send_message_en_texto_plano() -> None:
    requests: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json={"ok": True, "result": {}})

    bot = TelegramBot(TOKEN, transport=httpx2.MockTransport(handle))

    asyncio.run(bot.send_message(555, "hola"))

    (request,) = requests
    assert request.method == "POST"
    assert str(request.url) == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert json.loads(request.content) == {"chat_id": 555, "text": "hola"}


def test_ningun_registro_lleva_el_token_del_bot(caplog: pytest.LogCaptureFixture) -> None:
    # Principio VI: los logs no llevan claves. La URL de la Bot API lleva el token, y un cliente
    # HTTP que registre cada petición lo filtraría. Se captura todo, de cualquier logger, en DEBUG.
    caplog.set_level(logging.DEBUG)

    def handle(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"ok": True, "result": {}})

    bot = TelegramBot(TOKEN, transport=httpx2.MockTransport(handle))

    asyncio.run(bot.send_message(555, "hola"))

    assert caplog.records  # algo se registró: la captura funciona
    leaks = [record.name for record in caplog.records if TOKEN in record.getMessage()]
    assert leaks == []
