"""Textos que el bot de Telegram le envía al cliente (PED-93, HU-20).

Funciones puras: no tocan la base ni la red. Los precios salen del catálogo, nunca de la IA.
"""

from app.models.catalog import QuotableItem
from app.models.quote import Quote

# Límite de caracteres de un mensaje de la Bot API.
TELEGRAM_MAX_LENGTH = 4096

EMPTY_CATALOG_TEXT = "Todavía no hay productos disponibles."


def pesos(amount: int) -> str:
    """45000 → «$ 45.000». Sin depender de `app.templating`, que carga la capa web."""
    return "$ " + f"{amount:,}".replace(",", ".")


def catalog_text(items: list[QuotableItem]) -> str:
    """El catálogo: un ítem por línea, con su precio, en el orden de `list_quotable_items`."""
    if not items:
        return EMPTY_CATALOG_TEXT
    lines = [f"• {item.label}: {pesos(item.unit_price)}" for item in items]
    return "\n".join(
        [
            "Nuestro catálogo:",
            *lines,
            "",
            "Escríbeme qué quieres y cuántos, y te envío la cotización.",
        ]
    )


def start_text() -> str:
    """Saludo: qué escribir y cómo pedir el catálogo."""
    return (
        "¡Hola! Escríbeme lo que quieres pedir, con las cantidades, y te envío la cotización "
        "con nuestros precios. Para ver los productos disponibles, escribe /catalogo."
    )


def split_messages(text: str, limit: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Parte `text` en mensajes de como máximo `limit` caracteres, sin cortar líneas.

    Solo una línea más larga que el límite se corta, en trozos de `limit` caracteres.
    """
    pieces: list[str] = []
    for line in text.split("\n"):
        pieces.extend([line[i : i + limit] for i in range(0, len(line), limit)] or [""])
    parts: list[str] = []
    current: str | None = None
    for piece in pieces:
        if current is None:
            current = piece
        elif len(current) + 1 + len(piece) <= limit:
            current += "\n" + piece
        else:
            parts.append(current)
            current = piece
    if current is not None:
        parts.append(current)
    return parts


def quote_reply(quote: Quote, items: list[QuotableItem]) -> str:
    """Lo que el bot le responde al cliente sobre su cotización. Esqueleto de la Fase 3."""
    raise NotImplementedError


def owner_notice(quote: Quote, base_url: str) -> str | None:
    """El aviso al dueño, o `None` si la cotización no necesita su revisión. Esqueleto."""
    raise NotImplementedError
