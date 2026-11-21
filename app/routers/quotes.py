"""Páginas de cotización (PED-16, contracts/quote-pages.md)."""

from fastapi import APIRouter, Request
from pydantic_ai import Agent

from app.services.quote_ai import QuoteExtraction

router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])


def get_quote_extractor(request: Request) -> Agent[None, QuoteExtraction] | None:
    """Dependencia: el agente construido al arrancar (`app.state`), o `None` sin IA."""
    raise NotImplementedError
