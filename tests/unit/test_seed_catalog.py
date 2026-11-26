"""Pruebas de la siembra del catálogo de demostración (PED-102, app/services/seed_catalog.py)."""

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, select

from app.db import build_engine
from app.models.catalog import Product, ProductInput, ProductVariant, VariantInput, VariantKind
from app.services.catalog import add_variant, create_product, list_quotable_items
from app.services.seed_catalog import (
    SeedSummary,
    run_seed,
    seed_catalog,
)

# Lo que se puede cotizar tras sembrar sobre una base vacía: etiqueta y precio en pesos.
EXPECTED_ITEMS = {
    ("Alfajor", 2_500),
    ("Arepa de queso", 3_500),
    ("Buñuelo", 2_000),
    ("Café en vaso", 2_500),
    ("Empanada — Sabor: Carne", 2_500),
    ("Empanada — Sabor: Pollo", 2_500),
    ("Empanada — Sabor: Queso", 2_200),
    ("Galletas Festival — Sabor: Chocolate", 1_500),
    ("Galletas Festival — Sabor: Limón", 1_300),
    ("Galletas Festival — Sabor: Vainilla", 1_300),
    ("Gaseosa — Tamaño: 1,5 L", 5_500),
    ("Gaseosa — Tamaño: 400 ml", 2_500),
    ("Pan francés", 1_000),
    ("Pandebono", 2_200),
    ("Torta de chocolate — Tamaño: Grande", 60_000),
    ("Torta de chocolate — Tamaño: Mediana", 45_000),
    ("Torta de chocolate — Tamaño: Pequeña", 35_000),
    ("Torta de vainilla — Tamaño: Grande", 55_000),
    ("Torta de vainilla — Tamaño: Mediana", 42_000),
    ("Torta de vainilla — Tamaño: Pequeña", 32_000),
}
DEMO_PRODUCTS = 11
DEMO_VARIANTS = 14


def _quotable(session: Session) -> set[tuple[str, int]]:
    return {(item.label, item.unit_price) for item in list_quotable_items(session)}


def _rows(session: Session) -> tuple[int, int]:
    """Filas de productos y de variantes, activas o no."""
    products = len(session.exec(select(Product)).all())
    variants = len(session.exec(select(ProductVariant)).all())
    return products, variants


def test_sobre_una_base_vacia_carga_el_catalogo_de_demostracion(session: Session) -> None:
    summary = seed_catalog(session)

    assert _quotable(session) == EXPECTED_ITEMS
    assert summary == SeedSummary(
        products_created=DEMO_PRODUCTS,
        products_skipped=0,
        variants_created=DEMO_VARIANTS,
        variants_skipped=0,
    )


def test_sembrar_dos_veces_deja_lo_mismo_que_sembrar_una(session: Session) -> None:
    seed_catalog(session)
    after_first = (_quotable(session), _rows(session))

    second = seed_catalog(session)

    assert (_quotable(session), _rows(session)) == after_first
    assert _rows(session) == (DEMO_PRODUCTS, DEMO_VARIANTS)
    assert second == SeedSummary(
        products_created=0,
        products_skipped=DEMO_PRODUCTS,
        variants_created=0,
        variants_skipped=DEMO_VARIANTS,
    )


def test_respeta_lo_ya_cargado_y_solo_agrega_lo_que_falta(session: Session) -> None:
    # El dueño ya tiene el alfajor a otro precio y la torta con una sola variante; el nombre
    # se compara como en el resto del catálogo, sin mayúsculas ni tildes.
    create_product(session, ProductInput(name="alfajor", price=3_000))
    torta = create_product(session, ProductInput(name="TORTA DE CHOCOLATE", price=38_000))
    assert torta.id is not None
    add_variant(session, torta.id, VariantInput(kind=VariantKind.TAMANO, value="pequeña"))

    summary = seed_catalog(session)

    items = _quotable(session)
    assert ("alfajor", 3_000) in items
    assert ("Alfajor", 2_500) not in items
    # Con al menos una variante, recibe las que le faltan; la existente conserva su precio (el
    # del producto) y su escritura.
    assert ("TORTA DE CHOCOLATE — Tamaño: pequeña", 38_000) in items
    assert ("TORTA DE CHOCOLATE — Tamaño: Mediana", 45_000) in items
    assert ("TORTA DE CHOCOLATE — Tamaño: Grande", 60_000) in items
    assert not any(label.startswith("Torta de chocolate") for label, _ in items)
    assert summary == SeedSummary(
        products_created=DEMO_PRODUCTS - 2,
        products_skipped=2,
        variants_created=DEMO_VARIANTS - 1,
        variants_skipped=1,
    )


def test_un_producto_existente_sin_variantes_queda_intacto(session: Session) -> None:
    # Darle variantes cambiaría cómo se cotiza (R10): se omite entero, con sus variantes.
    empanada = create_product(session, ProductInput(name="Empanada", price=2_400))

    summary = seed_catalog(session)

    session.refresh(empanada)
    assert empanada.price == 2_400
    assert empanada.variants == []
    items = _quotable(session)
    assert ("Empanada", 2_400) in items
    assert not any(label.startswith("Empanada —") for label, _ in items)
    assert summary == SeedSummary(
        products_created=DEMO_PRODUCTS - 1,
        products_skipped=1,
        variants_created=DEMO_VARIANTS - 3,
        variants_skipped=3,
    )


def test_no_reactiva_ni_duplica_un_producto_desactivado(session: Session) -> None:
    bunuelo = create_product(session, ProductInput(name="Buñuelo", price=1_800))
    bunuelo.is_active = False
    session.add(bunuelo)
    session.commit()

    summary = seed_catalog(session)

    session.refresh(bunuelo)
    assert bunuelo.is_active is False
    assert bunuelo.price == 1_800
    assert not any(label == "Buñuelo" for label, _ in _quotable(session))
    assert summary.products_skipped == 1


def test_no_reactiva_ni_duplica_una_variante_desactivada(session: Session) -> None:
    empanada = create_product(session, ProductInput(name="Empanada", price=2_500))
    assert empanada.id is not None
    add_variant(session, empanada.id, VariantInput(kind=VariantKind.SABOR, value="Carne"))
    queso = add_variant(session, empanada.id, VariantInput(kind=VariantKind.SABOR, value="Queso"))
    queso.is_active = False
    session.add(queso)
    session.commit()

    summary = seed_catalog(session)

    session.refresh(queso)
    assert queso.is_active is False
    items = _quotable(session)
    assert not any(label == "Empanada — Sabor: Queso" for label, _ in items)
    assert ("Empanada — Sabor: Pollo", 2_500) in items
    assert summary.variants_created == DEMO_VARIANTS - 2
    assert summary.variants_skipped == 2


@pytest.fixture
def engine() -> Engine:
    seed_engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(seed_engine)
    return seed_engine


def test_run_seed_registra_un_resumen_sin_volcar_el_catalogo(
    engine: Engine, app_log: pytest.LogCaptureFixture
) -> None:
    app_log.set_level("INFO", logger="pedidofacil")

    run_seed(engine)
    run_seed(engine)

    messages = [record.getMessage() for record in app_log.records]
    assert messages == [
        "Catálogo de demostración: productos creados=11, omitidos=0; "
        "variantes creadas=14, omitidas=0",
        "Catálogo de demostración: productos creados=0, omitidos=11; "
        "variantes creadas=0, omitidas=14",
    ]
    log_text = "\n".join(messages)
    assert "Pandebono" not in log_text
    assert "2500" not in log_text
    assert "2.500" not in log_text


def test_run_seed_abre_y_cierra_su_propia_sesion(engine: Engine) -> None:
    summary = run_seed(engine)

    assert summary.products_created == DEMO_PRODUCTS
    with Session(engine) as check:
        assert _quotable(check) == EXPECTED_ITEMS
