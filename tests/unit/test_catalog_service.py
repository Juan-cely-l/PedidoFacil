"""Servicio del catálogo sobre SQLite en memoria (contracts/catalog-service.md)."""

import pytest
from sqlmodel import Session

from app.models.catalog import Product, ProductInput, ProductVariant, VariantInput
from app.repositories import catalog as catalog_repository
from app.services import catalog
from app.services.catalog import (
    DuplicateProductError,
    DuplicateVariantError,
    ProductNotFoundError,
)


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


# Variantes y fuente de precios (T020)


def variant_input(kind: str = "peso", value: str = "500 g", price: str = "") -> VariantInput:
    return VariantInput.model_validate({"kind": kind, "value": value, "price": price})


def create(session: Session, name: str, price: str = "18000") -> Product:
    return catalog.create_product(session, product_input(name, price=price))


def product_id(product: Product) -> int:
    assert product.id is not None
    return product.id


def deactivate(session: Session, item: Product | ProductVariant) -> None:
    item.is_active = False
    session.add(item)
    session.commit()


def test_agregar_variante_guarda_valor_limpio_y_clave_normalizada(session: Session) -> None:
    coffee = create(session, "Café")

    variant = catalog.add_variant(
        session, product_id(coffee), variant_input("peso", "  500   G ", "32.000")
    )

    assert variant.id is not None
    assert variant.product_id == coffee.id
    assert variant.kind == "peso"
    assert variant.value == "500 G"
    assert variant.value_key == "500 g"
    assert variant.price == 32000
    assert variant.is_active is True


def test_variante_repetida_en_el_mismo_producto_falla(session: Session) -> None:
    coffee = create(session, "Café")
    catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g"))

    with pytest.raises(DuplicateVariantError):
        catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 G "))


def test_mismo_valor_con_distinto_tipo_se_permite(session: Session) -> None:
    shirt = create(session, "Camiseta")
    catalog.add_variant(session, product_id(shirt), variant_input("color", "Negro"))

    variant = catalog.add_variant(session, product_id(shirt), variant_input("marca", "Negro"))

    assert variant.kind == "marca"


def test_misma_variante_en_otro_producto_se_permite(session: Session) -> None:
    coffee = create(session, "Café")
    sugar = create(session, "Azúcar")
    catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g"))

    variant = catalog.add_variant(session, product_id(sugar), variant_input("peso", "500 g"))

    assert variant.product_id == sugar.id


def test_variante_inactiva_no_impide_agregar_otra_igual(session: Session) -> None:
    coffee = create(session, "Café")
    old = catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g"))
    deactivate(session, old)

    new = catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g"))

    assert new.id != old.id


def test_agregar_variante_a_producto_inexistente_falla(session: Session) -> None:
    with pytest.raises(ProductNotFoundError):
        catalog.add_variant(session, 999, variant_input())


def test_variantes_simultaneas_iguales_las_frena_la_base(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_repository, "find_active_variant", lambda *_args, **_kwargs: None)
    coffee = create(session, "Café")
    catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g"))

    with pytest.raises(DuplicateVariantError):
        catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g"))

    # Tras el rollback la sesión sigue usable.
    assert catalog.get_product(session, product_id(coffee)).name == "Café"


def test_cotizables_producto_sin_variantes_se_cotiza_con_su_precio(session: Session) -> None:
    brownie = create(session, "Brownie", price="5.000")

    items = catalog.list_quotable_items(session)

    assert [(i.product_id, i.variant_id, i.label, i.unit_price) for i in items] == [
        (brownie.id, None, "Brownie", 5000)
    ]


def test_cotizables_producto_con_variantes_se_cotiza_solo_por_variante(
    session: Session,
) -> None:
    coffee = create(session, "Café", price="18.000")
    small = catalog.add_variant(session, product_id(coffee), variant_input("peso", "250 g"))
    large = catalog.add_variant(
        session, product_id(coffee), variant_input("peso", "500 g", "32.000")
    )

    items = catalog.list_quotable_items(session)

    assert [(i.product_id, i.variant_id, i.label, i.unit_price) for i in items] == [
        (coffee.id, small.id, "Café — Peso: 250 g", 18000),
        (coffee.id, large.id, "Café — Peso: 500 g", 32000),
    ]


def test_cotizables_excluyen_inactivos_y_ordenan_por_etiqueta(session: Session) -> None:
    coffee = create(session, "Café", price="18.000")
    catalog.add_variant(session, product_id(coffee), variant_input("peso", "500 g", "32.000"))
    kilo = catalog.add_variant(session, product_id(coffee), variant_input("peso", "1 kg"))
    deactivate(session, kilo)

    arequipe = create(session, "Arequipe", price="9.000")
    catalog.add_variant(session, product_id(arequipe), variant_input("tamano", "Grande"))
    deactivate(session, arequipe)

    cake = create(session, "Torta", price="40.000")
    chocolate = catalog.add_variant(session, product_id(cake), variant_input("sabor", "Chocolate"))
    deactivate(session, chocolate)

    create(session, "Brownie", price="5.000")

    labels = [(i.label, i.unit_price) for i in catalog.list_quotable_items(session)]

    assert labels == [
        ("Brownie", 5000),
        ("Café — Peso: 500 g", 32000),
        # Sin variantes activas, la torta vuelve a cotizarse como producto.
        ("Torta", 40000),
    ]
