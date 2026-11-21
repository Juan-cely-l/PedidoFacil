"""Servicio de cotización: del mensaje del cliente a un borrador con precios del catálogo.

La IA interpreta y el código calcula (principio V): los precios salen solo de
`list_quotable_items`. No importa FastAPI, Starlette, Jinja2, `app.config` ni `app.db`, para que
la ruta web y el webhook de Telegram (HU-20) llamen a las mismas funciones (RD-1, research R8).
"""

import asyncio
import datetime
import time

from pydantic import BaseModel
from pydantic_ai import Agent
from sqlmodel import Session

from app.models.catalog import QuotableItem
from app.models.quote import (
    MESSAGE_MAX_LENGTH,
    AiOutcome,
    LineStatus,
    Quote,
    QuoteLine,
    QuoteStatus,
    ReviewReason,
)
from app.repositories import quotes as repository
from app.services.catalog import list_quotable_items
from app.services.quote_ai import (
    ExtractedLine,
    QuoteExtraction,
    render_catalog_prompt,
    resolve_delivery_date,
    resolve_delivery_time,
)


class LineDraft(BaseModel):
    """Una línea calculada por el código a partir de la extracción, antes de guardarse.

    `label` y `unit_price` salen del `QuotableItem` del catálogo; son `None` si la línea está
    «Por revisar» (data-model.md).
    """

    customer_text: str | None
    product_id: int | None
    variant_id: int | None
    quantity: int | None
    quantity_assumed: bool
    status: LineStatus
    review_reason: ReviewReason | None
    label: str | None
    unit_price: int | None


class EmptyMessageError(Exception):
    """El mensaje está vacío o solo tiene espacios: no se llama a la IA."""


class MessageTooLongError(Exception):
    """El mensaje supera el máximo de caracteres: no se llama a la IA."""


class NothingToQuoteError(Exception):
    """No hay nada cotizable en el catálogo: no se llama a la IA."""


class QuoteNotFoundError(Exception):
    """La cotización no existe."""


def build_lines(extraction: QuoteExtraction, items: list[QuotableItem]) -> list[LineDraft]:
    """Convierte la extracción en líneas, con precios del catálogo (research.md R5).

    El precio y la etiqueta salen solo del `QuotableItem`: la extracción no tiene precios.
    """
    catalog = {(item.product_id, item.variant_id): item for item in items}
    return [_line_from(line, catalog) for line in extraction.lines]


def _line_from(
    line: ExtractedLine, catalog: dict[tuple[int, int | None], QuotableItem]
) -> LineDraft:
    item = catalog.get((line.product_id, line.variant_id)) if line.product_id else None
    if item is None or (line.quantity is not None and line.quantity < 1):
        # Las líneas «Por revisar» son de la Historia 2.
        raise NotImplementedError
    return LineDraft(
        customer_text=line.customer_text,
        product_id=item.product_id,
        variant_id=item.variant_id,
        quantity=line.quantity or 1,
        quantity_assumed=line.quantity is None,
        status=LineStatus.LISTA,
        review_reason=None,
        label=item.label,
        unit_price=item.unit_price,
    )


async def quote_message(  # noqa: PLR0913  (contrato: today y now se inyectan para las pruebas)
    session: Session,
    message: str,
    *,
    extractor: Agent[None, QuoteExtraction] | None,
    timeout_seconds: float,
    today: datetime.date,
    now: datetime.datetime,
) -> Quote:
    """Cotiza el mensaje y guarda el borrador (contracts/quote-service.md).

    Las validaciones van **antes** de llamar a la IA: un mensaje vacío, demasiado largo o un
    catálogo sin nada cotizable no gastan ninguna petición del proveedor (HU-20).
    """
    text = message.strip()
    if not text:
        raise EmptyMessageError
    if len(text) > MESSAGE_MAX_LENGTH:
        raise MessageTooLongError
    # Una sola lectura del catálogo: la misma lista arma el mensaje a la IA y valida su salida.
    items = list_quotable_items(session)
    if not items:
        raise NothingToQuoteError
    if extractor is None:
        # IA desactivada: Historia 3.
        raise NotImplementedError

    started = time.monotonic()
    async with asyncio.timeout(timeout_seconds):
        result = await extractor.run(render_catalog_prompt(items, text))
    duration_ms = round((time.monotonic() - started) * 1000)

    extraction = result.output
    delivery_date, date_needs_review = resolve_delivery_date(extraction.delivery_date, today)
    delivery_time, time_needs_review = resolve_delivery_time(extraction.delivery_time)
    quote = Quote(
        status=QuoteStatus.BORRADOR,
        customer_message=text,
        created_at=now,
        ai_outcome=AiOutcome.OK,
        ai_duration_ms=duration_ms,
        delivery_date=delivery_date,
        delivery_date_needs_review=date_needs_review,
        delivery_time=delivery_time,
        delivery_time_needs_review=time_needs_review,
        delivery_mode=extraction.delivery_mode,
        delivery_address=extraction.delivery_address,
        lines=[
            QuoteLine(position=position, **draft.model_dump())
            for position, draft in enumerate(build_lines(extraction, items), start=1)
        ],
    )
    return repository.save_quote(session, quote)


def get_quote(session: Session, quote_id: int) -> Quote:
    """Devuelve la cotización con sus líneas."""
    quote = repository.get_quote(session, quote_id)
    if quote is None:
        raise QuoteNotFoundError
    return quote


def list_quotes(session: Session) -> list[Quote]:
    """Cotizaciones de la más reciente a la más antigua."""
    return repository.list_quotes(session)


def line_subtotal(line: QuoteLine) -> int | None:
    """Precio unitario por cantidad, en pesos enteros; `None` si la línea no tiene precio."""
    if line.status != LineStatus.LISTA or line.unit_price is None or line.quantity is None:
        return None
    return line.unit_price * line.quantity


def quote_total(quote: Quote) -> int:
    """Suma, en pesos enteros, los subtotales de las líneas listas.

    Las líneas «Por revisar» no tienen precio y no suman (FR-010).
    """
    return sum(subtotal for line in quote.lines if (subtotal := line_subtotal(line)) is not None)


def pending_count(quote: Quote) -> int:
    """Número de líneas «Por revisar»."""
    return sum(1 for line in quote.lines if line.status == LineStatus.POR_REVISAR)
