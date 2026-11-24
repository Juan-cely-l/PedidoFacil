"""Cliente de la Bot API de Telegram (PED-93, HU-20), con llamadas directas por httpx2.

Sin librerías de bots (constitución, principio IV). Las pruebas le inyectan un
`httpx2.MockTransport`: nunca se llama a Telegram.
"""

import httpx2


class TelegramBot:
    """Envía mensajes de texto con el token del bot.

    Esqueleto de la Fase 1: todavía no envía nada.
    """

    def __init__(self, token: str, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self._token = token
        self._transport = transport

    async def send_message(self, chat_id: int, text: str) -> None:
        """Envía `text` al chat `chat_id`, en texto plano."""
        raise NotImplementedError
