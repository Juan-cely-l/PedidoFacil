"""Reglas del catálogo: unicidad de nombres y consulta de productos."""

from sqlmodel import Session

from app.models.catalog import Product, ProductInput


class ProductNotFoundError(Exception):
    """El producto pedido no existe."""


class DuplicateProductError(Exception):
    """Ya existe un producto activo con ese nombre."""


def create_product(session: Session, data: ProductInput) -> Product:
    """Crea un producto activo."""
    raise NotImplementedError


def list_products(session: Session, *, include_inactive: bool = False) -> list[Product]:
    """Productos del catálogo ordenados por nombre."""
    raise NotImplementedError


def get_product(session: Session, product_id: int) -> Product:
    """Producto por id."""
    raise NotImplementedError
