"""Cliente de la Bot API de Telegram (PED-93, HU-20), con llamadas directas por httpx2.

Sin librerías de bots (constitución, principio IV). Las pruebas le inyectan un
`httpx2.MockTransport`: nunca se llama a Telegram.
"""

import httpx2

API_URL = "https://api.telegram.org"
# Telegram suele responder en milisegundos; un tope evita colgar la tarea en segundo plano.
_TIMEOUT_SECONDS = 10


class TelegramBot:
    """Envía mensajes de texto con el token del bot."""

    def __init__(self, token: str, transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self._token = token
        self._transport = transport

    async def send_message(self, chat_id: int, text: str) -> None:
        """Envía `text` al chat `chat_id`, en texto plano (sin `parse_mode`, D6)."""
        async with httpx2.AsyncClient(
            base_url=API_URL, transport=self._transport, timeout=_TIMEOUT_SECONDS
        ) as client:
            response = await client.post(
                f"/bot{self._token}/sendMessage", json={"chat_id": chat_id, "text": text}
            )
            response.raise_for_status()
