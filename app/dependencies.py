"""Dependencias de FastAPI que comparten varios routers.

Aquí y no en un router, para que los routers dependan de servicios y no unos de otros
(routers → services → repositories). Es el equivalente de un bean compartido en Spring.
"""

from fastapi import Request
from pydantic_ai import Agent

from app.services.quote_ai import QuoteExtraction

QuoteExtractor = Agent[None, QuoteExtraction]


def get_quote_extractor(request: Request) -> QuoteExtractor | None:
    """Dependencia: el agente construido al arrancar (`app.state`), o `None` sin IA."""
    extractor: QuoteExtractor | None = request.app.state.quote_extractor
    return extractor
