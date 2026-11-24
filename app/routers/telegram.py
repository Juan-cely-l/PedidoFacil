"""Webhook del bot de Telegram (PED-93, HU-20; specs/005-bot-telegram/spec.md).

Lo protege el token secreto de Telegram, no la sesión del dueño (constitución, principio VI).
"""

from fastapi import APIRouter, Request, status
from fastapi.responses import Response

from app.services.telegram import TelegramBot

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105  (nombre de la cabecera)
WEBHOOK_PATH = "/telegram/webhook"

router = APIRouter(tags=["telegram"])


def get_telegram_bot(request: Request) -> TelegramBot:
    """Dependencia: el cliente de la Bot API. Esqueleto de la Fase 1."""
    raise NotImplementedError


@router.post(WEBHOOK_PATH, status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request) -> Response:
    """Recibe una actualización de Telegram. Esqueleto de la Fase 1."""
    raise NotImplementedError
