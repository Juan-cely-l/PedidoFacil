"""Páginas de cotización (PED-16, contracts/quote-pages.md).

Formularios HTML con Post/Redirect/Get, como el catálogo. La lógica vive en
`app/services/quotes.py`, que el bot de Telegram (HU-20) reutiliza tal cual.
"""

import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from pydantic_ai import Agent
from sqlmodel import Session

from app.config import Settings, get_app_settings
from app.db import get_session
from app.models.quote import AiOutcome, DeliveryInput, LineInput, Quote, QuoteLine, ReviewReason
from app.services import quotes
from app.services.catalog import list_quotable_items
from app.services.quote_ai import QuoteExtraction
from app.templating import COLOMBIA, templates

QUOTE_NOT_FOUND_MESSAGE = "La cotización no existe"
LINE_NOT_FOUND_MESSAGE = "La línea no existe"
DELIVERY_ERRORS = {
    "date": "Escribe una fecha válida",
    "time": "Escribe una hora válida (HH:MM)",
    "mode": "Elige domicilio o recoger",
    "address": "La dirección admite máximo 200 caracteres",
}
EMPTY_MESSAGE = "Pega el mensaje del cliente"
TOO_LONG_MESSAGE = "El mensaje es demasiado largo (máximo 2.000 caracteres)"
LINE_ERRORS = {
    "item": "Ese producto ya no está disponible en el catálogo",
    "quantity": "La cantidad debe ser un número entero entre 1 y 999",
}
# Sin detalles técnicos: qué pasó y qué puede hacer el dueño (contracts/quote-pages.md).
AI_NOTICES = {
    AiOutcome.TIMEOUT: "La IA no respondió a tiempo: agrega los productos a mano",
    AiOutcome.PROVIDER_ERROR: (
        "La IA no está disponible en este momento: agrega los productos a mano"
    ),
    AiOutcome.INVALID_OUTPUT: "La IA no entregó una respuesta válida: agrega los productos a mano",
    AiOutcome.DISABLED: "La IA está desactivada en este ambiente: agrega los productos a mano",
}
REVIEW_REASON_LABELS = {
    ReviewReason.NO_RECONOCIDO: "No está en el catálogo",
    ReviewReason.FALTA_VARIANTE: "Falta la presentación",
    ReviewReason.CANTIDAD_INVALIDA: "Cantidad no válida",
}

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])

QuoteExtractor = Agent[None, QuoteExtraction]


def get_quote_extractor(request: Request) -> QuoteExtractor | None:
    """Dependencia: el agente construido al arrancar (`app.state`), o `None` sin IA."""
    extractor: QuoteExtractor | None = request.app.state.quote_extractor
    return extractor


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
ExtractorDep = Annotated[QuoteExtractor | None, Depends(get_quote_extractor)]


def _new_form(
    request: Request,
    *,
    has_items: bool,
    message: str = "",
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "quotes/new.html",
        {"has_items": has_items, "message": message, "error": error},
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
def list_quotes(request: Request, session: SessionDep) -> HTMLResponse:
    """Cotizaciones de la más reciente a la más antigua, con su total y pendientes."""
    rows: list[dict[str, Any]] = [
        {"quote": quote, "total": quotes.quote_total(quote), "pending": quotes.pending_count(quote)}
        for quote in quotes.list_quotes(session)
    ]
    return templates.TemplateResponse(request, "quotes/list.html", {"rows": rows})


@router.get("/nueva", response_class=HTMLResponse)
def new_quote(request: Request, session: SessionDep) -> HTMLResponse:
    """Formulario para pegar el mensaje, o el aviso de crear productos primero."""
    return _new_form(request, has_items=bool(list_quotable_items(session)))


@router.post(
    "",
    response_class=HTMLResponse,
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        status.HTTP_409_CONFLICT: {"description": "No hay nada cotizable"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Mensaje vacío o demasiado largo"},
    },
)
async def create_quote(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    extractor: ExtractorDep,
    message: Annotated[str, Form()] = "",
) -> Response:
    """Cotiza el mensaje y redirige al borrador."""
    now = datetime.datetime.now(datetime.UTC)
    try:
        quote = await quotes.quote_message(
            session,
            message,
            extractor=extractor,
            timeout_seconds=settings.ai_timeout_seconds,
            today=now.astimezone(COLOMBIA).date(),
            now=now,
        )
    except quotes.EmptyMessageError:
        return _new_form(
            request,
            has_items=True,
            message=message,
            error=EMPTY_MESSAGE,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except quotes.MessageTooLongError:
        return _new_form(
            request,
            has_items=True,
            message=message,
            error=TOO_LONG_MESSAGE,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except quotes.NothingToQuoteError:
        return _new_form(request, has_items=False, status_code=status.HTTP_409_CONFLICT)
    return RedirectResponse(
        request.app.url_path_for("quote_detail", quote_id=quote.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/{quote_id}",
    name="quote_detail",
    response_class=HTMLResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": QUOTE_NOT_FOUND_MESSAGE}},
)
def quote_detail(request: Request, session: SessionDep, quote_id: int) -> HTMLResponse:
    """Borrador con sus líneas, precios del catálogo, total y datos de entrega."""
    return _detail(request, session, _get_quote_or_404(session, quote_id))


def _get_quote_or_404(session: Session, quote_id: int) -> Quote:
    try:
        return quotes.get_quote(session, quote_id)
    except quotes.QuoteNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, QUOTE_NOT_FOUND_MESSAGE) from error


def _detail(  # noqa: PLR0913  (cada formulario de la página conserva lo escrito)
    request: Request,
    session: Session,
    quote: Quote,
    *,
    form: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    line_forms: dict[int, dict[str, str]] | None = None,
    line_errors: dict[int, dict[str, str]] | None = None,
    delivery_form: dict[str, str] | None = None,
    delivery_errors: dict[str, str] | None = None,
) -> HTMLResponse:
    """El detalle; con errores en cualquier formulario, responde 422 y conserva lo escrito."""
    items = list_quotable_items(session)
    # Nombre del producto de una línea sin presentación (escenario 2.2), desde el catálogo.
    names = {item.product_id: item.label.partition(" — ")[0] for item in items}
    lines = [
        {
            "line": line,
            "subtotal": quotes.line_subtotal(line),
            "reason": (
                REVIEW_REASON_LABELS[ReviewReason(line.review_reason)]
                if line.review_reason
                else None
            ),
            "product_name": (
                names.get(line.product_id) if line.review_reason and line.product_id else None
            ),
            "form": (line_forms or {}).get(line.id or 0) or _line_form(line),
            "errors": (line_errors or {}).get(line.id or 0, {}),
        }
        for line in quote.lines
    ]
    has_errors = bool(errors or line_errors or delivery_errors)
    return templates.TemplateResponse(
        request,
        "quotes/detail.html",
        {
            "quote": quote,
            "lines": lines,
            "total": quotes.quote_total(quote),
            "pending": quotes.pending_count(quote),
            "notice": AI_NOTICES.get(AiOutcome(quote.ai_outcome)),
            "options": [{"value": quotes.item_key(item), "label": item.label} for item in items],
            "form": form or {"item": "", "quantity": "1"},
            "errors": errors or {},
            "delivery_form": delivery_form or _delivery_form(quote),
            "delivery_errors": delivery_errors or {},
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if has_errors else status.HTTP_200_OK,
    )


def _line_form(line: QuoteLine) -> dict[str, str]:
    """Lo que muestra el formulario de una línea antes de editarla."""
    item = ""
    if line.review_reason is None and line.product_id is not None:
        item = str(line.product_id)
        if line.variant_id is not None:
            item += f":{line.variant_id}"
    return {"item": item, "quantity": "" if line.quantity is None else str(line.quantity)}


def _delivery_form(quote: Quote) -> dict[str, str]:
    return {
        "date": quote.delivery_date.isoformat() if quote.delivery_date else "",
        "time": quote.delivery_time.strftime("%H:%M") if quote.delivery_time else "",
        "mode": quote.delivery_mode or "",
        "address": quote.delivery_address or "",
    }


def _field_errors(error: ValidationError, messages: dict[str, str]) -> dict[str, str]:
    return {str(detail["loc"][0]): messages[str(detail["loc"][0])] for detail in error.errors()}


@router.post(
    "/{quote_id}/lineas",
    response_class=HTMLResponse,
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": QUOTE_NOT_FOUND_MESSAGE},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Línea inválida"},
    },
)
def add_line(
    request: Request,
    session: SessionDep,
    quote_id: int,
    item: Annotated[str, Form()] = "",
    quantity: Annotated[str, Form()] = "",
) -> Response:
    """Agrega una línea a mano, con el precio del catálogo, y redirige al detalle."""
    quote = _get_quote_or_404(session, quote_id)
    form = {"item": item, "quantity": quantity}
    try:
        quotes.add_line(session, quote_id, LineInput.model_validate(form))
    except ValidationError as error:
        return _detail(request, session, quote, form=form, errors=_field_errors(error, LINE_ERRORS))
    except quotes.ItemNotQuotableError:
        errors = {"item": LINE_ERRORS["item"]}
        return _detail(request, session, quote, form=form, errors=errors)
    return RedirectResponse(
        request.app.url_path_for("quote_detail", quote_id=quote_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{quote_id}/lineas/{line_id}",
    response_class=HTMLResponse,
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "La cotización o la línea no existen"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Línea inválida"},
    },
)
def update_line(  # noqa: PLR0913, PLR0917  (la ruta y los dos campos del formulario)
    request: Request,
    session: SessionDep,
    quote_id: int,
    line_id: int,
    item: Annotated[str, Form()] = "",
    quantity: Annotated[str, Form()] = "",
) -> Response:
    """Corrige el ítem o la cantidad de una línea y redirige al detalle."""
    quote = _get_quote_or_404(session, quote_id)
    form = {"item": item, "quantity": quantity}
    try:
        quotes.update_line(session, quote_id, line_id, LineInput.model_validate(form))
    except quotes.QuoteLineNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, LINE_NOT_FOUND_MESSAGE) from error
    except ValidationError as error:
        errors = _field_errors(error, LINE_ERRORS)
        return _line_error(request, session, quote, line_id, form, errors)
    except quotes.ItemNotQuotableError:
        return _line_error(request, session, quote, line_id, form, {"item": LINE_ERRORS["item"]})
    return _to_detail(request, quote_id)


def _line_error(  # noqa: PLR0913, PLR0917  (la línea, lo escrito y sus errores)
    request: Request,
    session: Session,
    quote: Quote,
    line_id: int,
    form: dict[str, str],
    errors: dict[str, str],
) -> HTMLResponse:
    session.refresh(quote)  # la línea no cambió: se muestra como está guardada
    return _detail(
        request, session, quote, line_forms={line_id: form}, line_errors={line_id: errors}
    )


@router.post(
    "/{quote_id}/lineas/{line_id}/eliminar",
    response_class=HTMLResponse,
    status_code=status.HTTP_303_SEE_OTHER,
    responses={status.HTTP_404_NOT_FOUND: {"description": "La cotización o la línea no existen"}},
)
def remove_line(request: Request, session: SessionDep, quote_id: int, line_id: int) -> Response:
    """Elimina una línea y redirige al detalle."""
    _get_quote_or_404(session, quote_id)
    try:
        quotes.remove_line(session, quote_id, line_id)
    except quotes.QuoteLineNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, LINE_NOT_FOUND_MESSAGE) from error
    return _to_detail(request, quote_id)


@router.post(
    "/{quote_id}/entrega",
    response_class=HTMLResponse,
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": QUOTE_NOT_FOUND_MESSAGE},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Entrega inválida"},
    },
)
def update_delivery(  # noqa: PLR0913, PLR0917  (los cuatro campos del formulario)
    request: Request,
    session: SessionDep,
    quote_id: int,
    date: Annotated[str, Form()] = "",
    time: Annotated[str, Form()] = "",
    mode: Annotated[str, Form()] = "",
    address: Annotated[str, Form()] = "",
) -> Response:
    """Guarda la entrega y redirige al detalle; quita las marcas «por confirmar»."""
    quote = _get_quote_or_404(session, quote_id)
    form = {"date": date, "time": time, "mode": mode, "address": address}
    try:
        data = DeliveryInput.model_validate(form)
    except ValidationError as error:
        errors = _field_errors(error, DELIVERY_ERRORS)
        return _detail(request, session, quote, delivery_form=form, delivery_errors=errors)
    quotes.update_delivery(session, quote_id, data)
    return _to_detail(request, quote_id)


def _to_detail(request: Request, quote_id: int) -> RedirectResponse:
    return RedirectResponse(
        request.app.url_path_for("quote_detail", quote_id=quote_id),
        status_code=status.HTTP_303_SEE_OTHER,
    )
