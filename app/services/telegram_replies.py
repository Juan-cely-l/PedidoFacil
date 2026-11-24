"""Textos que el bot de Telegram le envía al cliente (PED-93, HU-20).

Funciones puras: no tocan la base ni la red. Los precios salen del catálogo, nunca de la IA.
Esqueleto de la Fase 2.
"""

from app.models.catalog import QuotableItem

# Límite de caracteres de un mensaje de la Bot API.
TELEGRAM_MAX_LENGTH = 4096


def catalog_text(items: list[QuotableItem]) -> str:
    """El catálogo: un ítem por línea, con su precio."""
    raise NotImplementedError


def start_text() -> str:
    """Saludo: qué escribir y cómo pedir el catálogo."""
    raise NotImplementedError


def split_messages(text: str, limit: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Parte `text` en mensajes de como máximo `limit` caracteres, sin cortar líneas."""
    raise NotImplementedError
