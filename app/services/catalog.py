"""Reglas del catálogo: unicidad de nombres y consulta de productos.

Es la única puerta al catálogo para los routers (equivale a un `@Service` de Spring); el
acceso a datos queda en `app.repositories.catalog`.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

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
    return _save(session, product, DuplicateProductError(product.name_key))


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
    """Agrega una variante activa al producto, si no tiene otra activa igual."""
    get_product(session, product_id)
    variant = ProductVariant(
        product_id=product_id,
        kind=data.kind.value,
        value=data.value,
        value_key=normalize_key(data.value),
        price=data.price,
    )
    if repository.find_active_variant(session, product_id, variant.kind, variant.value_key):
        raise DuplicateVariantError(variant.value_key)
    return _save(session, variant, DuplicateVariantError(variant.value_key))


def effective_price(product: Product, variant: ProductVariant) -> int:
    """Precio propio de la variante o, si no tiene, el vigente del producto (FR-006)."""
    return variant.price if variant.price is not None else product.price


def list_quotable_items(session: Session) -> list[QuotableItem]:
    """Lo que se puede cotizar hoy, con su precio efectivo: la única fuente de precios.

    Un producto con variantes activas se cotiza solo por ellas, para que el cliente elija
    siempre una presentación; sin variantes activas, se cotiza como producto (R10).
    """
    items: list[QuotableItem] = []
    for product in repository.list_active_products_with_variants(session):
        product_id = _required_id(product.id)
        variants = [variant for variant in product.variants if variant.is_active]
        if not variants:
            items.append(
                QuotableItem(
                    product_id=product_id,
                    variant_id=None,
                    label=product.name,
                    unit_price=product.price,
                )
            )
        items.extend(
            QuotableItem(
                product_id=product_id,
                variant_id=_required_id(variant.id),
                label=f"{product.name} — {variant.label}",
                unit_price=effective_price(product, variant),
            )
            for variant in variants
        )
    return sorted(items, key=lambda item: normalize_key(item.label))


def _ensure_unique_name(session: Session, name_key: str) -> None:
    """Verificación previa, para dar un mensaje claro antes de tocar la base."""
    if repository.find_active_product_by_key(session, name_key):
        raise DuplicateProductError(name_key)


def _save[Model: SQLModel](session: Session, obj: Model, duplicate: Exception) -> Model:
    """Guarda; si dos peticiones pasaron la verificación a la vez, el índice único decide.

    Los datos ya llegan validados, así que la única restricción que puede fallar aquí es la de
    unicidad entre activos: se traduce al error de dominio `duplicate`.
    """
    try:
        return repository.save(session, obj)
    except IntegrityError as error:
        session.rollback()
        raise duplicate from error


def _required_id(value: int | None) -> int:
    """Id de un registro ya guardado (siempre lo tiene tras el commit)."""
    if value is None:  # pragma: no cover - imposible tras guardar
        raise ValueError("registro sin id")
    return value
