"""Reglas del catálogo: unicidad de nombres y consulta de productos.

Es la única puerta al catálogo para los routers (equivale a un `@Service` de Spring); el
acceso a datos queda en `app.repositories.catalog`.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models.catalog import (
    Product,
    ProductInput,
    ProductVariant,
    QuotableItem,
    VariantInput,
    normalize_key,
)
from app.repositories import catalog as repository


class ProductNotFoundError(Exception):
    """El producto pedido no existe."""


class DuplicateProductError(Exception):
    """Ya existe un producto activo con ese nombre."""


class DuplicateVariantError(Exception):
    """El producto ya tiene una variante activa con ese tipo y valor."""


def create_product(session: Session, data: ProductInput) -> Product:
    """Crea un producto activo, si no hay otro activo con el mismo nombre."""
    product = Product(
        name=data.name,
        name_key=normalize_key(data.name),
        description=data.description,
        price=data.price,
        tracks_inventory=data.tracks_inventory,
    )
    _ensure_unique_name(session, product.name_key)
    return _save(session, product)


def list_products(session: Session, *, include_inactive: bool = False) -> list[Product]:
    """Productos del catálogo ordenados por nombre."""
    return repository.list_products(session, include_inactive=include_inactive)


def get_product(session: Session, product_id: int) -> Product:
    """Producto por id."""
    product = repository.get_product(session, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    return product


def add_variant(session: Session, product_id: int, data: VariantInput) -> ProductVariant:
    """Agrega una variante activa al producto."""
    raise NotImplementedError


def effective_price(product: Product, variant: ProductVariant) -> int:
    """Precio propio de la variante o, si no tiene, el del producto."""
    raise NotImplementedError


def list_quotable_items(session: Session) -> list[QuotableItem]:
    """Lo que se puede cotizar hoy, con su precio efectivo (única fuente de precios)."""
    raise NotImplementedError


def _ensure_unique_name(session: Session, name_key: str) -> None:
    """Verificación previa, para dar un mensaje claro antes de tocar la base."""
    if repository.find_active_product_by_key(session, name_key):
        raise DuplicateProductError(name_key)


def _save(session: Session, product: Product) -> Product:
    """Guarda; si dos peticiones pasaron la verificación a la vez, el índice único decide.

    Los datos ya llegan validados, así que la única restricción que puede fallar aquí es la de
    nombre único entre activos.
    """
    try:
        return repository.save(session, product)
    except IntegrityError as error:
        session.rollback()
        raise DuplicateProductError(product.name_key) from error
