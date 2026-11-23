"""Cotizaciones y sus líneas (PED-16, specs/004-cotizacion-con-ia/data-model.md).

La línea guarda el precio y la etiqueta copiados del catálogo al cotizar; los subtotales y el
total no se guardan, se calculan al leer (research.md R9). Ningún precio sale de la IA.
"""

import datetime
import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator
from pydantic import Field as InputField
from pydantic_core import PydanticCustomError
from sqlalchemy import CheckConstraint, Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

MESSAGE_MAX_LENGTH = 2000
CUSTOMER_TEXT_MAX_LENGTH = 200
LABEL_MAX_LENGTH = 200
ADDRESS_MAX_LENGTH = 200
MAX_QUANTITY = 999
# «<product_id>» o «<product_id>:<variant_id>». [0-9] y no \d, que acepta dígitos no latinos.
_ITEM_PATTERN = r"^[0-9]+(:[0-9]+)?$"
# Lo que envían <input type="date"> y <input type="time">: formatos fijos, sin interpretaciones.
_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TIME_PATTERN = re.compile(r"[0-9]{2}:[0-9]{2}")


class QuoteStatus(StrEnum):
    """Estado de la cotización. En esta historia solo existe el borrador (HU-16 y HU-17 suman)."""

    BORRADOR = "borrador"


class AiOutcome(StrEnum):
    """Cómo terminó la consulta a la IA (research.md R4 y R12)."""

    OK = "ok"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_OUTPUT = "invalid_output"
    DISABLED = "disabled"


class DeliveryMode(StrEnum):
    """Modalidad de entrega."""

    DOMICILIO = "domicilio"
    RECOGER = "recoger"


class LineStatus(StrEnum):
    """Una línea lista suma al total; una por revisar espera al dueño."""

    LISTA = "lista"
    POR_REVISAR = "por_revisar"


class ReviewReason(StrEnum):
    """Por qué una línea quedó «Por revisar» (research.md R5)."""

    NO_RECONOCIDO = "no_reconocido"
    FALTA_VARIANTE = "falta_variante"
    CANTIDAD_INVALIDA = "cantidad_invalida"


def _sql_values(enum: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum)


class Quote(SQLModel, table=True):
    """Cotización generada a partir del mensaje de un cliente."""

    __table_args__ = (
        CheckConstraint(f"status IN ({_sql_values(QuoteStatus)})", name="ck_quote_status"),
        CheckConstraint(f"ai_outcome IN ({_sql_values(AiOutcome)})", name="ck_quote_ai_outcome"),
        CheckConstraint(
            f"delivery_mode IS NULL OR delivery_mode IN ({_sql_values(DeliveryMode)})",
            name="ck_quote_delivery_mode",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    status: str = Field(default=QuoteStatus.BORRADOR, max_length=12)
    customer_message: str = Field(max_length=MESSAGE_MAX_LENGTH)
    # La lista se ordena por fecha de creación, de la más reciente a la más antigua.
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    ai_outcome: str = Field(max_length=16)
    ai_duration_ms: int | None = None
    delivery_date: datetime.date | None = None
    delivery_date_needs_review: bool = False
    delivery_time: datetime.time | None = None
    delivery_time_needs_review: bool = False
    delivery_mode: str | None = Field(default=None, max_length=10)
    delivery_mode_needs_review: bool = False
    delivery_address: str | None = Field(default=None, max_length=ADDRESS_MAX_LENGTH)

    lines: list["QuoteLine"] = Relationship(
        back_populates="quote",
        sa_relationship_kwargs={
            "order_by": "QuoteLine.position",
            "cascade": "all, delete-orphan",
        },
    )


class QuoteLine(SQLModel, table=True):
    """Línea de una cotización: lista (con precio del catálogo) o por revisar (sin precio)."""

    __tablename__ = "quote_line"
    __table_args__ = (
        CheckConstraint(f"status IN ({_sql_values(LineStatus)})", name="ck_quote_line_status"),
        CheckConstraint(
            f"review_reason IS NULL OR review_reason IN ({_sql_values(ReviewReason)})",
            name="ck_quote_line_review_reason",
        ),
        CheckConstraint(
            f"quantity IS NULL OR quantity BETWEEN 1 AND {MAX_QUANTITY}",
            name="ck_quote_line_quantity",
        ),
        CheckConstraint("unit_price IS NULL OR unit_price > 0", name="ck_quote_line_unit_price"),
        CheckConstraint(
            "variant_id IS NULL OR product_id IS NOT NULL", name="ck_quote_line_variant_product"
        ),
        # Invariante de línea (data-model.md): una lista tiene todo para sumar al total; una
        # por revisar no tiene precio y sí un motivo.
        CheckConstraint(
            "(status = 'lista' AND product_id IS NOT NULL AND unit_price IS NOT NULL "
            "AND quantity IS NOT NULL AND label IS NOT NULL AND review_reason IS NULL) "
            "OR (status = 'por_revisar' AND unit_price IS NULL AND review_reason IS NOT NULL)",
            name="ck_quote_line_invariant",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    quote_id: int = Field(foreign_key="quote.id", ondelete="CASCADE", index=True)
    position: int
    customer_text: str | None = Field(default=None, max_length=CUSTOMER_TEXT_MAX_LENGTH)
    status: str = Field(max_length=12)
    review_reason: str | None = Field(default=None, max_length=20)
    # RESTRICT: el catálogo nunca se borra, solo se desactiva (research.md R9).
    product_id: int | None = Field(default=None, foreign_key="product.id", ondelete="RESTRICT")
    variant_id: int | None = Field(
        default=None, foreign_key="product_variant.id", ondelete="RESTRICT"
    )
    # Copiados del catálogo al cotizar o al cambiar el ítem; no cambian si el catálogo cambia.
    label: str | None = Field(default=None, max_length=LABEL_MAX_LENGTH)
    unit_price: int | None = None
    quantity: int | None = None
    quantity_assumed: bool = False

    quote: Quote | None = Relationship(back_populates="lines")


class LineInput(BaseModel):
    """Una línea que el dueño arma a mano: ítem cotizable y cantidad, nunca un precio (FR-014)."""

    item: Annotated[str, StringConstraints(pattern=_ITEM_PATTERN)]
    quantity: Annotated[int, InputField(ge=1, le=MAX_QUANTITY)]


class DeliveryInput(BaseModel):
    """Entrega que corrige el dueño, tal como llega del formulario: textos, vacíos si no hay dato.

    Valida el formato; `parsed_date`, `parsed_time`, `parsed_mode` y `parsed_address` dan los
    valores para guardar.
    """

    date: str = ""
    time: str = ""
    mode: str = ""
    address: str = ""

    @field_validator("date", "time", "mode", "address")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("date")
    @classmethod
    def _valid_date(cls, value: str) -> str:
        if value and not (_DATE_PATTERN.fullmatch(value) and _is_iso_date(value)):
            raise PydanticCustomError("date_invalid", "fecha inválida")
        return value

    @field_validator("time")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        if value and not (_TIME_PATTERN.fullmatch(value) and _is_iso_time(value)):
            raise PydanticCustomError("time_invalid", "hora inválida")
        return value

    @field_validator("mode")
    @classmethod
    def _valid_mode(cls, value: str) -> str:
        if value and value not in {mode.value for mode in DeliveryMode}:
            raise PydanticCustomError("mode_invalid", "modalidad desconocida")
        return value

    @field_validator("address")
    @classmethod
    def _valid_address(cls, value: str) -> str:
        if len(value) > ADDRESS_MAX_LENGTH:
            raise PydanticCustomError("address_too_long", "dirección demasiado larga")
        return value

    @property
    def parsed_date(self) -> datetime.date | None:
        return datetime.date.fromisoformat(self.date) if self.date else None

    @property
    def parsed_time(self) -> datetime.time | None:
        return datetime.time.fromisoformat(self.time) if self.time else None

    @property
    def parsed_mode(self) -> DeliveryMode | None:
        return DeliveryMode(self.mode) if self.mode else None

    @property
    def parsed_address(self) -> str | None:
        return self.address or None


def _is_iso_date(value: str) -> bool:
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_iso_time(value: str) -> bool:
    try:
        datetime.time.fromisoformat(value)
    except ValueError:
        return False
    return True
