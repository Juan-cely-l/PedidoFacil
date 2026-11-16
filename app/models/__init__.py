"""Modelos de dominio y de entrada (SQLModel).

Importar este paquete registra todas las tablas en `SQLModel.metadata` (lo usa Alembic).
"""

from app.models.catalog import Product, ProductInput

__all__ = ["Product", "ProductInput"]
