"""Webhook del bot de Telegram (PED-93, HU-20; specs/005-bot-telegram/spec.md).

Lo protege el token secreto de Telegram, no la sesión del dueño (constitución, principio VI).
Responde 200 de inmediato y atiende el mensaje en segundo plano (D4): si tardara o fallara,
Telegram reintentaría la misma actualización.
"""

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import Engine
from sqlmodel import Session

from app.config import Settings, get_app_settings
from app.services.catalog import list_quotable_items
from app.services.telegram import TelegramBot
from app.services.telegram_replies import catalog_text, split_messages, start_text

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105  (nombre de la cabecera)
WEBHOOK_PATH = "/telegram/webhook"
NOT_CONFIGURED_MESSAGE = "El bot de Telegram no está configurado"
INVALID_SECRET_MESSAGE = "Token secreto inválido"  # noqa: S105  (mensaje de error)
CATALOG_COMMAND = "/catalogo"

router = APIRouter(tags=["telegram"])


def get_telegram_bot(request: Request) -> TelegramBot | None:
    """Dependencia: el cliente de la Bot API construido al arrancar, o `None` sin bot."""
    bot: TelegramBot | None = request.app.state.telegram_bot
    return bot


@router.post(
    WEBHOOK_PATH,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": INVALID_SECRET_MESSAGE},
        status.HTTP_404_NOT_FOUND: {"description": NOT_CONFIGURED_MESSAGE},
    },
)
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_app_settings)],
    bot: Annotated[TelegramBot | None, Depends(get_telegram_bot)],
    secret: Annotated[str | None, Header(alias=SECRET_HEADER)] = None,
) -> Response:
    """Recibe una actualización de Telegram, solo con el secreto correcto."""
    if not settings.telegram_enabled or settings.telegram_webhook_secret is None or bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_CONFIGURED_MESSAGE)
    expected = settings.telegram_webhook_secret.get_secret_value()
    # Comparación en tiempo constante: no revela cuántos caracteres coinciden.
    if secret is None or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_SECRET_MESSAGE)
    # El cuerpo se lee solo después de validar el secreto.
    message = _text_message(await request.json())
    if message is not None:
        chat_id, text = message
        background.add_task(_answer, bot, request.app.state.engine, chat_id, text)
    return Response(status_code=status.HTTP_200_OK)


def _text_message(update: Any) -> tuple[int, str] | None:
    """El chat y el texto de un mensaje nuevo; `None` para cualquier otra actualización."""
    message = update.get("message") if isinstance(update, dict) else None
    if not isinstance(message, dict):
        return None
    text, chat = message.get("text"), message.get("chat")
    if not isinstance(text, str) or not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    return (chat_id, text) if isinstance(chat_id, int) else None


async def _answer(bot: TelegramBot, engine: Engine, chat_id: int, text: str) -> None:
    """Responde un mensaje de texto. Corre después de responder 200 a Telegram."""
    if not text.startswith("/"):
        return  # cotizar: Fase 3
    # En grupos, Telegram agrega el nombre del bot: «/catalogo@MiBot».
    command = text.split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
    if command == CATALOG_COMMAND:
        # Sesión propia: la de la petición ya se cerró cuando corre esta tarea.
        with Session(engine) as session:
            reply = catalog_text(list_quotable_items(session))
    else:
        reply = start_text()
    for part in split_messages(reply):
        await bot.send_message(chat_id, part)
