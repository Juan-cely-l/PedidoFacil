"""Servicio del catálogo sobre SQLite en memoria (contracts/catalog-service.md)."""

import pytest
from sqlmodel import Session

from app.models.catalog import ProductInput
from app.repositories import catalog as catalog_repository
from app.services import catalog
from app.services.catalog import DuplicateProductError, ProductNotFoundError


def product_input(
    name: str = "Brownie",
    *,
    price: str = "5000",
    description: str = "",
    tracks_inventory: bool = False,
) -> ProductInput:
    return ProductInput.model_validate(
        {
            "name": name,
            "price": price,
            "description": description,
            "tracks_inventory": tracks_inventory,
        }
    )


def test_crear_producto_guarda_la_clave_normalizada_y_queda_activo(session: Session) -> None:
    product = catalog.create_product(
        session, product_input("  Brownie  de Chocolate ", price="5.000", tracks_inventory=True)
    )

    assert product.id is not None
    assert product.name == "Brownie de Chocolate"
    assert product.name_key == "brownie de chocolate"
    assert product.price == 5000
    assert product.tracks_inventory is True
    assert product.is_active is True


def test_crear_producto_con_nombre_activo_repetido_falla(session: Session) -> None:
    catalog.create_product(session, product_input("Brownie"))

    with pytest.raises(DuplicateProductError):
        catalog.create_product(session, product_input("brownie "))


def test_crear_producto_distingue_la_enie(session: Session) -> None:
    catalog.create_product(session, product_input("Piña"))

    product = catalog.create_product(session, product_input("Pina"))

    assert product.name == "Pina"


def test_producto_inactivo_no_impide_crear_otro_con_el_mismo_nombre(session: Session) -> None:
    old = catalog.create_product(session, product_input("Brownie"))
    old.is_active = False
    session.add(old)
    session.commit()

    new = catalog.create_product(session, product_input("Brownie"))

    assert new.id != old.id
    assert new.is_active is True


def test_listar_productos_ordena_por_nombre_y_oculta_inactivos(session: Session) -> None:
    for name in ["torta", "Arequipe", "brownie"]:
        catalog.create_product(session, product_input(name))
    inactive = catalog.create_product(session, product_input("Bocadillo"))
    inactive.is_active = False
    session.add(inactive)
    session.commit()

    active_names = [product.name for product in catalog.list_products(session)]
    all_names = [product.name for product in catalog.list_products(session, include_inactive=True)]

    assert active_names == ["Arequipe", "brownie", "torta"]
    assert all_names == ["Arequipe", "Bocadillo", "brownie", "torta"]


def test_obtener_producto_existente(session: Session) -> None:
    created = catalog.create_product(session, product_input("Brownie"))
    assert created.id is not None

    assert catalog.get_product(session, created.id).name == "Brownie"


def test_obtener_producto_inexistente_falla(session: Session) -> None:
    with pytest.raises(ProductNotFoundError):
        catalog.get_product(session, 999)


def test_guardados_simultaneos_con_el_mismo_nombre_los_frena_la_base(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simula dos peticiones que pasan la verificación previa a la vez: solo queda el índice.
    monkeypatch.setattr(
        catalog_repository, "find_active_product_by_key", lambda *_args, **_kwargs: None
    )
    catalog.create_product(session, product_input("Brownie"))

    with pytest.raises(DuplicateProductError):
        catalog.create_product(session, product_input("Brownie"))

    # Tras el rollback la sesión sigue usable.
    assert [product.name for product in catalog.list_products(session)] == ["Brownie"]
