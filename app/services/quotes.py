"""Servicio de cotización: del mensaje del cliente a un borrador con precios del catálogo.

La IA interpreta y el código calcula (principio V): los precios salen solo de
`list_quotable_items`. No importa FastAPI, Starlette, Jinja2, `app.config` ni `app.db`, para que
la ruta web y el webhook de Telegram (HU-20) llamen a las mismas funciones (RD-1, research R8).
"""

import datetime

from pydantic import BaseModel
from pydantic_ai import Agent
from sqlmodel import Session

from app.models.catalog import QuotableItem
from app.models.quote import LineStatus, Quote, ReviewReason
from app.services.quote_ai import QuoteExtraction


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
    """Convierte la extracción en líneas, con precios del catálogo (research.md R5)."""
    raise NotImplementedError


async def quote_message(  # noqa: PLR0913  (contrato: today y now se inyectan para las pruebas)
    session: Session,
    message: str,
    *,
    extractor: Agent[None, QuoteExtraction] | None,
    timeout_seconds: float,
    today: datetime.date,
    now: datetime.datetime,
) -> Quote:
    """Cotiza el mensaje y guarda el borrador (contracts/quote-service.md)."""
    raise NotImplementedError


def get_quote(session: Session, quote_id: int) -> Quote:
    """Devuelve la cotización con sus líneas."""
    raise NotImplementedError


def list_quotes(session: Session) -> list[Quote]:
    """Cotizaciones de la más reciente a la más antigua."""
    raise NotImplementedError


def quote_total(quote: Quote) -> int:
    """Suma, en pesos enteros, los subtotales de las líneas listas."""
    raise NotImplementedError


def pending_count(quote: Quote) -> int:
    """Número de líneas «Por revisar»."""
    raise NotImplementedError
