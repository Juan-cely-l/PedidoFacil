"""Textos que el bot de Telegram le envía al cliente (PED-93, HU-20).

Funciones puras: no tocan la base ni la red. Los precios salen del catálogo, nunca de la IA.
"""

from itertools import groupby

from app.models.catalog import QuotableItem
from app.models.quote import AiOutcome, LineStatus, Quote, QuoteLine, ReviewReason
from app.services.quotes import line_subtotal, quote_total

# Límite de caracteres de un mensaje de la Bot API.
TELEGRAM_MAX_LENGTH = 4096

EMPTY_CATALOG_TEXT = "Todavía no hay productos disponibles."
TOO_LONG_TEXT = "Tu mensaje es demasiado largo; envíamelo más corto, por favor."
REVIEW_TEXT = "Recibimos tu mensaje; el dueño lo revisará."
# Cierto desde PED-101 (26/11): el dueño recibe aviso de toda cotización, con el @usuario.
DONE_TEXT = "El negocio ya recibió tu cotización y te escribirá para confirmarla."
SEPARATOR = "—" * 16
NO_ORDER_TEXT = (
    "No encontré un pedido en tu mensaje. Escríbeme los productos y las cantidades, "
    "o escribe /catalogo para ver lo que tenemos."
)


def pesos(amount: int) -> str:
    """45000 → «$ 45.000». Sin depender de `app.templating`, que carga la capa web."""
    return "$ " + f"{amount:,}".replace(",", ".")


def catalog_text(items: list[QuotableItem]) -> str:
    """El catálogo, un bloque por producto: el nombre solo, y debajo cada variante con su precio.

    En el orden de `list_quotable_items`. Texto plano (D6): saltos de línea, sin tablas.
    """
    if not items:
        return EMPTY_CATALOG_TEXT
    blocks = ["Nuestro catálogo\n" + SEPARATOR]
    for _, group in groupby(items, key=lambda item: item.product_id):
        product_items = list(group)
        lines = [product_items[0].label.partition(" — ")[0]]
        for item in product_items:
            variant = item.label.partition(" — ")[2]
            price = pesos(item.unit_price)
            lines.append(f"   • {variant} — {price}" if variant else f"   {price}")
        blocks.append("\n".join(lines))
    blocks.append("Escríbeme qué quieres y cuántos, y te envío la cotización.")
    return "\n\n".join(blocks)


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
    # Bloques separados por una línea en blanco: líneas, total, pendientes y cierre.
    blocks: list[str] = []
    if ready:
        lines = ["Tu cotización", SEPARATOR]
        for line in ready:
            subtotal = pesos(line_subtotal(line) or 0)
            lines.append(f"• {line.label}")
            lines.append(f"   {line.quantity} x {pesos(line.unit_price or 0)} = {subtotal}")
        blocks.append("\n".join(lines))
        blocks.append(f"Total: {pesos(quote_total(quote))}")
    if pending:
        blocks.append(
            "\n".join(["Por revisar:", *(_pending_line(line, items) for line in pending)])
        )
    blocks.append(DONE_TEXT if ready else catalog_text(items))
    return "\n\n".join(blocks)


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


def owner_notice(quote: Quote, base_url: str, *, customer_username: str | None) -> str | None:
    """El aviso al dueño de toda cotización, con el motivo si hay algo que revisar (D7).

    `None` solo para un mensaje sin pedido (cero líneas, escenario 9): no hay nada que confirmar.

    Lleva el @usuario del cliente para que el dueño le escriba desde su cuenta; si no tiene, lo
    dice. Es un mensaje privado al dueño: ese dato nunca va a los logs (principio VI).
    """
    link = f"{base_url}/cotizaciones/{quote.id}"
    if quote.ai_outcome != AiOutcome.OK:
        reason = ": la IA no pudo procesarla"
    elif not quote.lines:
        return None
    elif pending := sum(1 for line in quote.lines if line.status == LineStatus.POR_REVISAR):
        reason = f": {pending} línea(s) por revisar"
    else:
        reason = ""
    contact = (
        f"Cliente: @{customer_username}"
        if customer_username
        else "El cliente no tiene usuario de Telegram."
    )
    return f"Cotización n.º {quote.id} por Telegram{reason}.\n{contact}\nRevísala: {link}"
