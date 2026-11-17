"""Consultas y persistencia del catálogo."""

from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, col, select

from app.models.catalog import Product, ProductVariant


def get_product(session: Session, product_id: int) -> Product | None:
    """Busca un producto por id."""
    return session.get(Product, product_id)


def list_products(session: Session, *, include_inactive: bool) -> list[Product]:
    """Productos ordenados por nombre; solo los activos salvo que se pidan todos."""
    statement = select(Product).order_by(col(Product.name_key), col(Product.id))
    if not include_inactive:
        statement = statement.where(col(Product.is_active))
    return list(session.exec(statement).all())


def find_active_product_by_key(session: Session, name_key: str) -> Product | None:
    """Producto activo con esa clave de nombre."""
    statement = select(Product).where(col(Product.name_key) == name_key, col(Product.is_active))
    return session.exec(statement).first()


def save[Model: SQLModel](session: Session, obj: Model) -> Model:
    """Guarda el registro y lo devuelve con su id."""
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def find_active_variant(
    session: Session, product_id: int, kind: str, value_key: str
) -> ProductVariant | None:
    """Variante activa del producto con ese tipo y valor."""
    statement = select(ProductVariant).where(
        col(ProductVariant.product_id) == product_id,
        col(ProductVariant.kind) == kind,
        col(ProductVariant.value_key) == value_key,
        col(ProductVariant.is_active),
    )
    return session.exec(statement).first()


def list_active_products_with_variants(session: Session) -> list[Product]:
    """Productos activos con sus variantes cargadas en una sola consulta extra (sin N+1)."""
    statement = (
        select(Product).where(col(Product.is_active)).options(selectinload(Product.variants))  # type: ignore[arg-type]
    )
    return list(session.exec(statement).all())
