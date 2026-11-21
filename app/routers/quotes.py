"""Páginas de cotización (PED-16, contracts/quote-pages.md).

Formularios HTML con Post/Redirect/Get, como el catálogo. La lógica vive en
`app/services/quotes.py`, que el bot de Telegram (HU-20) reutiliza tal cual.
"""

import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic_ai import Agent
from sqlmodel import Session

from app.config import Settings, get_app_settings
from app.db import get_session
from app.services import quotes
from app.services.catalog import list_quotable_items
from app.services.quote_ai import QuoteExtraction
from app.templating import COLOMBIA, templates

QUOTE_NOT_FOUND_MESSAGE = "La cotización no existe"
EMPTY_MESSAGE = "Pega el mensaje del cliente"
TOO_LONG_MESSAGE = "El mensaje es demasiado largo (máximo 2.000 caracteres)"

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
    try:
        quote = quotes.get_quote(session, quote_id)
    except quotes.QuoteNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, QUOTE_NOT_FOUND_MESSAGE) from error
    lines = [{"line": line, "subtotal": quotes.line_subtotal(line)} for line in quote.lines]
    return templates.TemplateResponse(
        request,
        "quotes/detail.html",
        {"quote": quote, "lines": lines, "total": quotes.quote_total(quote)},
    )
