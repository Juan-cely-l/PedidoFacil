"""Catálogo de productos: reglas de dominio, tablas y datos de entrada."""

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError
from sqlalchemy import CheckConstraint, Index, text
from sqlmodel import Field, SQLModel

MAX_PRICE = 100_000_000
NAME_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 200

NAME_REQUIRED_MESSAGE = "El nombre es obligatorio"
NAME_TOO_LONG_MESSAGE = "El nombre admite máximo 100 caracteres"
DESCRIPTION_TOO_LONG_MESSAGE = "La descripción admite máximo 200 caracteres"

PRICE_INVALID_MESSAGE = "El precio debe ser un número entero mayor que cero"
PRICE_GROUPING_MESSAGE = (
    "Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos"
)
PRICE_TOO_HIGH_MESSAGE = "El precio supera 100.000.000; revisa si hay un error de digitación"

_PLAIN_DIGITS = re.compile(r"[0-9]+")
# Miles agrupados de a tres con punto o espacio; \s incluye los espacios no separables.
_THOUSANDS_GROUPED = re.compile(r"[0-9]{1,3}(?:[.\s][0-9]{3})+")
_DIGITS_AND_SEPARATORS = re.compile(r"[0-9.\s]+")
_NON_DIGITS = re.compile(r"[^0-9]")

_COMBINING_TILDE = "̃"


def parse_price(raw: str) -> int:
    """Convierte el precio escrito en el formulario a pesos enteros.

    Admite «45000», «45.000» y «45 000». Un punto que no agrupa tres dígitos («45.00») se
    rechaza en lugar de interpretarse en silencio, y la coma nunca se acepta: los pesos no
    llevan centavos.
    """
    text = raw.strip()
    if not (_PLAIN_DIGITS.fullmatch(text) or _THOUSANDS_GROUPED.fullmatch(text)):
        if _DIGITS_AND_SEPARATORS.fullmatch(text) and any(char.isdigit() for char in text):
            raise PydanticCustomError("price_grouping", PRICE_GROUPING_MESSAGE)
        raise PydanticCustomError("price_invalid", PRICE_INVALID_MESSAGE)

    value = int(_NON_DIGITS.sub("", text))
    if value < 1:
        raise PydanticCustomError("price_invalid", PRICE_INVALID_MESSAGE)
    if value > MAX_PRICE:
        raise PydanticCustomError("price_too_high", PRICE_TOO_HIGH_MESSAGE)
    return value


def clean_text(text: str) -> str:
    """Recorta y colapsa los espacios internos, sin cambiar mayúsculas ni tildes."""
    return " ".join(text.split())


def normalize_key(text: str) -> str:
    """Clave para comparar nombres: sin mayúsculas, tildes ni espacios sobrantes.

    La ñ se conserva porque no es una tilde: cambia la palabra («Piña» ≠ «Pina»).
    """
    decomposed = unicodedata.normalize("NFD", clean_text(text).casefold())
    kept: list[str] = []
    for char in decomposed:
        is_enie_tilde = char == _COMBINING_TILDE and kept[-1:] == ["n"]
        if unicodedata.combining(char) and not is_enie_tilde:
            continue
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept))


class Product(SQLModel, table=True):
    """Algo que vende el negocio, con su precio en pesos enteros."""

    __table_args__ = (
        CheckConstraint(f"price > 0 AND price <= {MAX_PRICE}", name="ck_product_price_range"),
        # Solo entre activos: un producto desactivado puede repetir nombre.
        Index(
            "ux_product_active_name",
            "name_key",
            unique=True,
            sqlite_where=text("is_active"),
            postgresql_where=text("is_active"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=NAME_MAX_LENGTH)
    name_key: str = Field(max_length=NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=DESCRIPTION_MAX_LENGTH)
    price: int
    tracks_inventory: bool = False
    is_active: bool = True


class ProductInput(BaseModel):
    """Datos del formulario de producto, ya validados (equivale a un DTO con Bean Validation)."""

    name: str
    description: str = ""
    price: int
    tracks_inventory: bool = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        name = clean_text(value)
        if not name:
            raise PydanticCustomError("name_required", NAME_REQUIRED_MESSAGE)
        if len(name) > NAME_MAX_LENGTH:
            raise PydanticCustomError("name_too_long", NAME_TOO_LONG_MESSAGE)
        return name

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        description = value.strip()
        if len(description) > DESCRIPTION_MAX_LENGTH:
            raise PydanticCustomError("description_too_long", DESCRIPTION_TOO_LONG_MESSAGE)
        return description

    @field_validator("price", mode="before")
    @classmethod
    def _validate_price(cls, value: object) -> int:
        return parse_price(str(value))


class VariantKind(StrEnum):
    """Tipos de variante admitidos (se guardan como texto en la base)."""

    SABOR = "sabor"
    PESO = "peso"
    COLOR = "color"
    MARCA = "marca"
    TAMANO = "tamano"

    @property
    def label(self) -> str:
        """Nombre para mostrar en la interfaz."""
        raise NotImplementedError


class ProductVariant(SQLModel, table=True):
    """Presentación de un producto (sabor, peso, color, marca o tamaño)."""

    __tablename__ = "product_variant"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    kind: str = Field(max_length=10)
    value: str = Field(max_length=50)
    value_key: str = Field(max_length=50)
    price: int | None = None
    is_active: bool = True


class VariantInput(BaseModel):
    """Datos del formulario de variante, ya validados."""

    kind: VariantKind
    value: str
    price: int | None = None


class QuotableItem(BaseModel):
    """Algo que se puede cotizar, con su precio efectivo en pesos."""

    product_id: int
    variant_id: int | None
    label: str
    unit_price: int
