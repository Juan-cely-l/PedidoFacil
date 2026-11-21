"""Conversión de la extracción en líneas (research R5): el precio sale del catálogo, nunca de la IA.

Historia 1: los ítems cotizables válidos dan líneas «Lista». Los casos «Por revisar» son de la
Historia 2. El banco de mensajes es la entrada: si la IA acierta, el código no pierde nada.
"""

import pytest

from app.models.catalog import QuotableItem
from app.models.quote import LineStatus
from app.services.quote_ai import QuoteExtraction
from app.services.quotes import LineDraft, build_lines
from tests.banco_mensajes import CATALOGOS, MENSAJES, CasoBanco, puntuar
from tests.doubles import EMPTY_EXTRACTION, extraction_from_bank, line_payload

REPOSTERIA = CATALOGOS["reposteria"]
# Ids del catálogo fijo de repostería (tests/banco_mensajes.py).
TORTA_CHOCOLATE, MEDIANA, GRANDE = 1, 102, 103
ALFAJOR = 5


def _extraction(*lines: dict[str, object]) -> QuoteExtraction:
    return QuoteExtraction.model_validate({**EMPTY_EXTRACTION, "lines": list(lines)})


def _item(catalog: list[QuotableItem], product_id: int, variant_id: int | None) -> QuotableItem:
    return next(
        item for item in catalog if item.product_id == product_id and item.variant_id == variant_id
    )


def test_un_producto_sin_variantes_da_una_linea_lista_con_precio_del_catalogo() -> None:
    lines = build_lines(_extraction(line_payload(ALFAJOR, None, 3, "tres alfajores")), REPOSTERIA)

    assert lines == [
        LineDraft(
            customer_text="tres alfajores",
            product_id=ALFAJOR,
            variant_id=None,
            quantity=3,
            quantity_assumed=False,
            status=LineStatus.LISTA,
            review_reason=None,
            label="Alfajor",
            unit_price=2500,
        )
    ]


def test_una_variante_toma_su_etiqueta_y_su_precio_no_los_del_producto() -> None:
    (line,) = build_lines(_extraction(line_payload(TORTA_CHOCOLATE, GRANDE, 1)), REPOSTERIA)

    assert line.status == LineStatus.LISTA
    assert line.label == "Torta de chocolate — Tamaño: Grande"
    assert line.unit_price == 60000


def test_sin_cantidad_se_asume_1_y_se_marca() -> None:
    (line,) = build_lines(_extraction(line_payload(TORTA_CHOCOLATE, MEDIANA, None)), REPOSTERIA)

    assert line.quantity == 1
    assert line.quantity_assumed is True
    assert line.status == LineStatus.LISTA


def test_las_lineas_conservan_el_orden_del_mensaje() -> None:
    lines = build_lines(
        _extraction(
            line_payload(ALFAJOR, None, 12),
            line_payload(TORTA_CHOCOLATE, MEDIANA, 1),
            line_payload(TORTA_CHOCOLATE, GRANDE, 2),
        ),
        REPOSTERIA,
    )

    assert [(line.product_id, line.variant_id) for line in lines] == [
        (ALFAJOR, None),
        (TORTA_CHOCOLATE, MEDIANA),
        (TORTA_CHOCOLATE, GRANDE),
    ]


def test_los_precios_de_las_lineas_son_enteros() -> None:
    lines = build_lines(_extraction(line_payload(TORTA_CHOCOLATE, MEDIANA, 2)), REPOSTERIA)

    assert all(type(line.unit_price) is int for line in lines)


# Banco de mensajes (research R14)

CASOS_LISTOS = [
    caso
    for caso in MENSAJES
    if caso.esperado and all(item.status == "lista" for item in caso.esperado)
]


@pytest.mark.parametrize("caso", CASOS_LISTOS, ids=lambda caso: caso.id)
def test_si_la_ia_acierta_el_codigo_no_pierde_nada(caso: CasoBanco) -> None:
    catalog = CATALOGOS[caso.negocio]
    extraction = QuoteExtraction.model_validate(extraction_from_bank(caso))

    lines = build_lines(extraction, catalog)

    assert puntuar(caso.esperado, lines).valor == 1.0
    for line in lines:
        assert line.product_id is not None
        assert line.unit_price == _item(catalog, line.product_id, line.variant_id).unit_price


def test_r10_el_precio_sale_del_catalogo_y_no_del_mensaje() -> None:
    # El cliente dice «estaba en 40 mil»; el catálogo dice 45.000. La extracción no puede traer
    # precio (el esquema lo prohíbe), así que la línea solo puede tomarlo del catálogo.
    caso = next(caso for caso in MENSAJES if caso.id == "R10")
    assert "40 mil" in caso.texto

    (line,) = build_lines(
        QuoteExtraction.model_validate(extraction_from_bank(caso)), CATALOGOS[caso.negocio]
    )

    assert line.unit_price == 45000
    assert line.unit_price != 40000
