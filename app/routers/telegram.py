"""Webhook del bot de Telegram (PED-93, HU-20; specs/005-bot-telegram/spec.md).

Lo protege el token secreto de Telegram, no la sesión del dueño (constitución, principio VI).
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response

from app.config import Settings, get_app_settings
from app.services.telegram import TelegramBot

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105  (nombre de la cabecera)
WEBHOOK_PATH = "/telegram/webhook"
NOT_CONFIGURED_MESSAGE = "El bot de Telegram no está configurado"
INVALID_SECRET_MESSAGE = "Token secreto inválido"  # noqa: S105  (mensaje de error)

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
    settings: Annotated[Settings, Depends(get_app_settings)],
    secret: Annotated[str | None, Header(alias=SECRET_HEADER)] = None,
) -> Response:
    """Recibe una actualización de Telegram, solo con el secreto correcto."""
    if not settings.telegram_enabled or settings.telegram_webhook_secret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_CONFIGURED_MESSAGE)
    expected = settings.telegram_webhook_secret.get_secret_value()
    # Comparación en tiempo constante: no revela cuántos caracteres coinciden.
    if secret is None or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_SECRET_MESSAGE)
    return Response(status_code=status.HTTP_200_OK)
