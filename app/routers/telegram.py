"""Webhook del bot de Telegram (PED-93, HU-20; specs/005-bot-telegram/spec.md).

Lo protege el token secreto de Telegram, no la sesión del dueño (constitución, principio VI).
Responde 200 de inmediato y atiende el mensaje en segundo plano (D4): si tardara o fallara,
Telegram reintentaría la misma actualización.
"""

import datetime
import hmac
import logging
from typing import Annotated, Any

import httpx2
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import Engine
from sqlmodel import Session

from app.config import Settings, get_app_settings
from app.dependencies import QuoteExtractor, get_quote_extractor
from app.services import quotes
from app.services.catalog import list_quotable_items
from app.services.telegram import TelegramBot
from app.services.telegram_replies import (
    EMPTY_CATALOG_TEXT,
    TOO_LONG_TEXT,
    catalog_text,
    owner_notice,
    quote_reply,
    split_messages,
    start_text,
)
from app.templating import COLOMBIA

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105  (nombre de la cabecera)
WEBHOOK_PATH = "/telegram/webhook"
NOT_CONFIGURED_MESSAGE = "El bot de Telegram no está configurado"
INVALID_SECRET_MESSAGE = "Token secreto inválido"  # noqa: S105  (mensaje de error)
CATALOG_COMMAND = "/catalogo"

router = APIRouter(tags=["telegram"])
logger = logging.getLogger("pedidofacil.telegram")


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
async def telegram_webhook(  # noqa: PLR0913, PLR0917  (dependencias de FastAPI)
    request: Request,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_app_settings)],
    bot: Annotated[TelegramBot | None, Depends(get_telegram_bot)],
    extractor: Annotated[QuoteExtractor | None, Depends(get_quote_extractor)],
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
        reply = _Reply(bot, request.app.state.engine, settings, extractor)
        background.add_task(reply.answer, chat_id, text)
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


class _Reply:
    """Atiende un mensaje después de responder 200 a Telegram, con su propia sesión."""

    def __init__(
        self,
        bot: TelegramBot,
        engine: Engine,
        settings: Settings,
        extractor: QuoteExtractor | None,
    ) -> None:
        self.bot, self.engine, self.settings, self.extractor = bot, engine, settings, extractor

    async def answer(self, chat_id: int, text: str) -> None:
        """Responde un comando o cotiza el mensaje."""
        if text.startswith("/"):
            await self._send(chat_id, self._command(text))
            return
        reply, notice = await self._quote(text)
        await self._send(chat_id, reply)
        owner_chat = self.settings.owner_telegram_chat_id
        if notice is not None and owner_chat is not None:
            await self._send(owner_chat, notice)

    def _command(self, text: str) -> str:
        # En grupos, Telegram agrega el nombre del bot: «/catalogo@MiBot».
        command = text.split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
        if command != CATALOG_COMMAND:
            return start_text()
        # Sesión propia: la de la petición ya se cerró cuando corre esta tarea.
        with Session(self.engine) as session:
            return catalog_text(list_quotable_items(session))

    async def _quote(self, text: str) -> tuple[str, str | None]:
        """Cotiza con el servicio de HU-08, igual que la web; devuelve la respuesta y el aviso."""
        now = datetime.datetime.now(datetime.UTC)
        with Session(self.engine) as session:
            try:
                quote = await quotes.quote_message(
                    session,
                    text,
                    extractor=self.extractor,
                    timeout_seconds=self.settings.ai_timeout_seconds,
                    today=now.astimezone(COLOMBIA).date(),
                    now=now,
                )
            except quotes.MessageTooLongError:
                return TOO_LONG_TEXT, None
            except quotes.NothingToQuoteError:
                return EMPTY_CATALOG_TEXT, None
            reply = quote_reply(quote, list_quotable_items(session))
            notice = owner_notice(quote, self.settings.public_base_url or "")
        return reply, notice

    async def _send(self, chat_id: int, text: str) -> None:
        """Envía en partes de hasta 4096 caracteres; si Telegram falla, registra solo el tipo."""
        for part in split_messages(text):
            try:
                await self.bot.send_message(chat_id, part)
            except httpx2.HTTPError as error:
                # Ni el texto, ni el chat, ni la URL: la URL de la Bot API lleva el token.
                logger.warning("No se pudo enviar a Telegram: error=%s", type(error).__name__)
                return
