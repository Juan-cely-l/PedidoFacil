"""Catálogo de productos: reglas de dominio, tablas y datos de entrada."""

PRICE_INVALID_MESSAGE = "El precio debe ser un número entero mayor que cero"
PRICE_GROUPING_MESSAGE = (
    "Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos"
)
PRICE_TOO_HIGH_MESSAGE = "El precio supera 100.000.000; revisa si hay un error de digitación"


def parse_price(raw: str) -> int:
    """Convierte el precio escrito en el formulario a pesos enteros."""
    raise NotImplementedError


def clean_text(text: str) -> str:
    """Recorta y colapsa los espacios internos, sin cambiar mayúsculas ni tildes."""
    raise NotImplementedError


def normalize_key(text: str) -> str:
    """Clave para comparar nombres: sin mayúsculas, tildes ni espacios sobrantes."""
    raise NotImplementedError
