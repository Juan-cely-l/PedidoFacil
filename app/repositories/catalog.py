"""Consultas y persistencia del catálogo."""

from sqlmodel import Session, col, select

from app.models.catalog import Product


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


def save(session: Session, product: Product) -> Product:
    """Guarda el producto y lo devuelve con su id."""
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
