"""Contrato con el proveedor de IA para cotizar un mensaje (PED-16, research.md R5 y R6).

Aquí viven el esquema de lo que devuelve la IA (sin ningún campo de precio), las instrucciones y
la construcción del agente. No importa FastAPI, Starlette, Jinja2 ni `app.config`: el bot de
Telegram (HU-20) lo reutiliza tal cual (RD-1, research.md R8).
"""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent

from app.models.catalog import QuotableItem

MAX_LINES = 30


class _AiOutput(BaseModel):
    """Base de la salida de la IA: un campo de más (un precio, por ejemplo) la invalida (R5)."""

    model_config = ConfigDict(extra="forbid")


class DateExpression(_AiOutput):
    """La fecha tal como la dijo el cliente; el código la convierte (research.md R7)."""

    kind: Literal["today", "offset", "weekday", "day_of_month", "absolute", "unknown"]
    days: int | None = Field(default=None, ge=0, le=60, description="offset: días desde hoy")
    weekday: int | None = Field(default=None, ge=0, le=6, description="0 = lunes … 6 = domingo")
    day: int | None = Field(default=None, ge=1, le=31, description="day_of_month: día del mes")
    # Se llama como el campo del contrato; por eso el tipo va con el módulo completo.
    date: datetime.date | None = Field(default=None, description="absolute: fecha completa")


class ExtractedLine(_AiOutput):
    """Un pedido del mensaje. Sin precio: el precio sale del catálogo (principio V)."""

    customer_text: str = Field(
        min_length=1, max_length=200, description="Lo que escribió el cliente para este pedido"
    )
    product_id: int | None = Field(
        default=None, description="Id de la lista del catálogo, o null si no estás seguro"
    )
    variant_id: int | None = Field(default=None, description="Id de la variante, o null")
    quantity: int | None = Field(default=None, description="Cantidad, o null si no la dijo")


class QuoteExtraction(_AiOutput):
    """Todo lo que la IA identifica en el mensaje. No tiene precios, subtotales ni totales."""

    lines: list[ExtractedLine] = Field(default_factory=list, max_length=MAX_LINES)
    delivery_date: DateExpression | None = None
    # Texto libre: la normaliza el código (research.md R7b). Un formato estricto haría que una
    # hora mal escrita invalidara toda la extracción.
    delivery_time: str | None = Field(
        default=None,
        min_length=1,
        max_length=40,
        description="La hora tal como la dijo el cliente, sin convertirla",
    )
    delivery_mode: Literal["domicilio", "recoger"] | None = None
    delivery_address: str | None = Field(default=None, max_length=200)


INSTRUCTIONS = ""


def render_catalog_prompt(items: list[QuotableItem], message: str) -> str:
    """Arma el mensaje de usuario: `<catalogo>` sin precios y `<mensaje_cliente>` (R6)."""
    raise NotImplementedError


def resolve_delivery_date(
    expr: DateExpression | None, today: datetime.date
) -> tuple[datetime.date | None, bool]:
    """Convierte la expresión de fecha en una fecha y una marca de revisión (R7)."""
    raise NotImplementedError


def resolve_delivery_time(expr: str | None) -> tuple[datetime.time | None, bool]:
    """Normaliza la expresión de hora en una hora y una marca de revisión (R7b)."""
    raise NotImplementedError


def build_quote_agent(
    *,
    provider: Literal["fake", "gemini"],
    api_key: str | None,
    model_name: str,
    fallback_model_name: str | None,
    timeout_seconds: float,
) -> Agent[None, QuoteExtraction] | None:
    """Construye el agente de cotización; `None` si la IA está desactivada (R12)."""
    raise NotImplementedError
