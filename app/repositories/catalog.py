"""Consultas y persistencia del catálogo."""

from sqlmodel import Session

from app.models.catalog import Product


def get_product(session: Session, product_id: int) -> Product | None:
    """Busca un producto por id."""
    raise NotImplementedError


def list_products(session: Session, *, include_inactive: bool) -> list[Product]:
    """Productos ordenados por nombre; solo los activos salvo que se pidan todos."""
    raise NotImplementedError


def find_active_product_by_key(
    session: Session, name_key: str, *, exclude_id: int | None = None
) -> Product | None:
    """Producto activo con esa clave de nombre, sin contar el de `exclude_id`."""
    raise NotImplementedError


def save(session: Session, product: Product) -> Product:
    """Guarda el producto y lo devuelve con su id."""
    raise NotImplementedError
