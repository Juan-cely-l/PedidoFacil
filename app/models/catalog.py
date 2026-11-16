"""Catálogo de productos: reglas de dominio, tablas y datos de entrada."""

import re
import unicodedata

from pydantic_core import PydanticCustomError

MAX_PRICE = 100_000_000

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
