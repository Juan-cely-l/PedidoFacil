"""Siembra idempotente del catálogo de demostración (PED-102).

Se activa con SEED_DEMO_CATALOG al arrancar la app, o a mano con scripts/seed_catalog.py.
Crea solo lo que falta, por nombre, con los servicios del catálogo; nunca modifica, reactiva ni
desactiva lo que el dueño ya cargó.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session

from app.models.catalog import Product, ProductInput, VariantInput, VariantKind, normalize_key
from app.services.catalog import add_variant, create_product, list_products


@dataclass(frozen=True)
class DemoProduct:
    """Producto de demostración: precio propio, o variantes de un tipo con su precio."""

    name: str
    price: int | None = None
    kind: VariantKind | None = None
    variants: tuple[tuple[str, int], ...] = ()


# El catálogo, como dato: montos enteros en pesos y nombres como los escribiría una clienta.
DEMO_CATALOG: tuple[DemoProduct, ...] = (
    DemoProduct(
        "Galletas Festival",
        kind=VariantKind.SABOR,
        variants=(("Limón", 1_300), ("Vainilla", 1_300), ("Chocolate", 1_500)),
    ),
    DemoProduct(
        "Torta de chocolate",
        kind=VariantKind.TAMANO,
        variants=(("Pequeña", 35_000), ("Mediana", 45_000), ("Grande", 60_000)),
    ),
    DemoProduct(
        "Torta de vainilla",
        kind=VariantKind.TAMANO,
        variants=(("Pequeña", 32_000), ("Mediana", 42_000), ("Grande", 55_000)),
    ),
    DemoProduct(
        "Empanada",
        kind=VariantKind.SABOR,
        variants=(("Carne", 2_500), ("Pollo", 2_500), ("Queso", 2_200)),
    ),
    DemoProduct(
        "Gaseosa",
        kind=VariantKind.TAMANO,
        variants=(("400 ml", 2_500), ("1,5 L", 5_500)),
    ),
    DemoProduct("Pan francés", price=1_000),
    DemoProduct("Pandebono", price=2_200),
    DemoProduct("Arepa de queso", price=3_500),
    DemoProduct("Buñuelo", price=2_000),
    DemoProduct("Alfajor", price=2_500),
    DemoProduct("Café en vaso", price=2_500),
)

logger = logging.getLogger("pedidofacil.seed")


@dataclass(frozen=True)
class SeedSummary:
    """Cuántos productos y variantes se crearon y cuántos se omitieron por existir ya."""

    products_created: int
    products_skipped: int
    variants_created: int
    variants_skipped: int


def seed_catalog(session: Session, catalog: tuple[DemoProduct, ...] = DEMO_CATALOG) -> SeedSummary:
    """Crea lo que falta del catálogo y devuelve el resumen.

    Un producto existente (activo o no) se omite. Solo si tiene al menos una variante activa
    recibe las que le faltan: darle variantes a uno que no tiene cambiaría cómo se cotiza (R10).
    Una variante existente, activa o no, se omite.
    """
    # Activos al final: ante un nombre repetido entre desactivados, gana el activo.
    loaded = sorted(list_products(session, include_inactive=True), key=lambda p: p.is_active)
    existing = {product.name_key: product for product in loaded}

    products_created = products_skipped = variants_created = variants_skipped = 0
    for demo in catalog:
        product = existing.get(normalize_key(demo.name))
        if product is None:
            product = create_product(session, ProductInput(name=demo.name, price=_base_price(demo)))
            products_created += 1
            missing = demo.variants
        else:
            products_skipped += 1
            missing = _missing_variants(product, demo)
            variants_skipped += len(demo.variants) - len(missing)
        for value, price in missing:
            add_variant(
                session,
                _required_id(product.id),
                VariantInput(kind=_required_kind(demo), value=value, price=price),
            )
            variants_created += 1
    return SeedSummary(products_created, products_skipped, variants_created, variants_skipped)


def run_seed(engine: Engine) -> SeedSummary:
    """Siembra con su propia sesión y registra solo el resumen, nunca el catálogo."""
    with Session(engine) as session:
        summary = seed_catalog(session)
    logger.info(
        "Catálogo de demostración: productos creados=%d, omitidos=%d; "
        "variantes creadas=%d, omitidas=%d",
        summary.products_created,
        summary.products_skipped,
        summary.variants_created,
        summary.variants_skipped,
    )
    return summary


def _base_price(demo: DemoProduct) -> int:
    """Precio del producto: el propio o, con variantes, el menor de ellas."""
    if demo.price is not None:
        return demo.price
    return min(price for _, price in demo.variants)


def _missing_variants(product: Product, demo: DemoProduct) -> tuple[tuple[str, int], ...]:
    """Variantes de la demostración que el producto no tiene, si ya tiene alguna activa."""
    if not demo.variants or not product.is_active:
        return ()
    if not any(variant.is_active for variant in product.variants):
        return ()
    kind = _required_kind(demo).value
    loaded = {variant.value_key for variant in product.variants if variant.kind == kind}
    return tuple(
        (value, price) for value, price in demo.variants if normalize_key(value) not in loaded
    )


def _required_kind(demo: DemoProduct) -> VariantKind:
    if demo.kind is None:  # pragma: no cover - el catálogo siempre declara el tipo
        raise ValueError(f"{demo.name}: variantes sin tipo")
    return demo.kind


def _required_id(value: int | None) -> int:
    if value is None:  # pragma: no cover - imposible tras guardar
        raise ValueError("registro sin id")
    return value
