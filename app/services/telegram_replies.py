"""Textos que el bot de Telegram le envía al cliente (PED-93, HU-20).

Funciones puras: no tocan la base ni la red. Los precios salen del catálogo, nunca de la IA.
"""

from app.models.catalog import QuotableItem
from app.models.quote import AiOutcome, LineStatus, Quote, QuoteLine, ReviewReason
from app.services.quotes import line_subtotal, quote_total

# Límite de caracteres de un mensaje de la Bot API.
TELEGRAM_MAX_LENGTH = 4096

EMPTY_CATALOG_TEXT = "Todavía no hay productos disponibles."
TOO_LONG_TEXT = "Tu mensaje es demasiado largo; envíamelo más corto, por favor."
REVIEW_TEXT = "Recibimos tu pedido; el dueño lo revisará y te escribirá."
DONE_TEXT = "El dueño te confirmará el pedido."
NO_ORDER_TEXT = (
    "No encontré un pedido en tu mensaje. Escríbeme los productos y las cantidades, "
    "o escribe /catalogo para ver lo que tenemos."
)


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
    """Lo que el bot le responde al cliente sobre su cotización.

    Los montos salen del `Quote` guardado, que los tomó del catálogo; nunca de la IA ni del
    mensaje (principio V). No lleva ids, nombres de modelos ni errores (FR-03).
    """
    if quote.ai_outcome != AiOutcome.OK:
        return REVIEW_TEXT
    if not quote.lines:
        return NO_ORDER_TEXT
    ready = [line for line in quote.lines if line.status == LineStatus.LISTA]
    pending = [line for line in quote.lines if line.status == LineStatus.POR_REVISAR]
    parts: list[str] = []
    if ready:
        parts.append("Tu cotización:")
        parts.extend(
            f"• {line.label} (cantidad {line.quantity}): {pesos(line_subtotal(line) or 0)}"
            for line in ready
        )
        parts.append(f"Total: {pesos(quote_total(quote))}")
    if pending:
        parts.extend(["", "No pude cotizar esto:"])
        parts.extend(_pending_line(line, items) for line in pending)
    if ready:
        parts.extend(["", DONE_TEXT])
    else:
        parts.extend(["", catalog_text(items)])
    return "\n".join(parts)


def _pending_line(line: QuoteLine, items: list[QuotableItem]) -> str:
    quoted = f"• «{line.customer_text}»"
    if line.review_reason == ReviewReason.FALTA_VARIANTE:
        variants = [
            item.label.partition(" — ")[2]
            for item in items
            if item.product_id == line.product_id and item.variant_id is not None
        ]
        return f"{quoted}: ¿qué presentación? Tenemos: {', '.join(variants)}."
    if line.review_reason == ReviewReason.CANTIDAD_INVALIDA:
        return f"{quoted}: la cantidad no es válida."
    return f"{quoted}: no lo encontré."


def owner_notice(quote: Quote, base_url: str) -> str | None:
    """El aviso al dueño, o `None` si la cotización no necesita su revisión (D7)."""
    link = f"{base_url}/cotizaciones/{quote.id}"
    if quote.ai_outcome != AiOutcome.OK:
        return f"Cotización n.º {quote.id} por Telegram: la IA no pudo procesarla. Revísala: {link}"
    pending = sum(1 for line in quote.lines if line.status == LineStatus.POR_REVISAR)
    if pending:
        return (
            f"Cotización n.º {quote.id} por Telegram: {pending} línea(s) por revisar. "
            f"Revísala: {link}"
        )
    return None
