"""Modelos de dominio y de entrada (SQLModel).

Importar este paquete registra todas las tablas en `SQLModel.metadata` (lo usa Alembic).
"""

from app.models.catalog import (
    Product,
    ProductInput,
    ProductVariant,
    QuotableItem,
    VariantInput,
    VariantKind,
)
from app.models.quote import (
    AiOutcome,
    DeliveryMode,
    LineStatus,
    Quote,
    QuoteLine,
    QuoteStatus,
    ReviewReason,
)

__all__ = [
    "AiOutcome",
    "DeliveryMode",
    "LineStatus",
    "Product",
    "ProductInput",
    "ProductVariant",
    "QuotableItem",
    "Quote",
    "QuoteLine",
    "QuoteStatus",
    "ReviewReason",
    "VariantInput",
    "VariantKind",
]
