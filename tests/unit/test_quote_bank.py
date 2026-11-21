"""Pruebas del banco de mensajes y de su puntuación (tests/banco_mensajes.py, research R14).

Los invariantes son guardas sobre datos ya aprobados por el autor: pasan desde el rojo y fallan
si alguien edita el banco y rompe una regla. La puntuación sí es código nuevo.
"""

import re
from typing import Any

import pytest

from app.models.quote import LineStatus, ReviewReason
from app.services import quotes
from tests.banco_mensajes import (
    CATALOGOS,
    MENSAJES,
    Acierto,
    CasoBanco,
    ItemEsperado,
    puntuar,
)

# Invariantes del banco (guardas)


def test_el_banco_tiene_al_menos_12_mensajes() -> None:
    assert len(MENSAJES) >= 12


def test_los_ids_de_los_casos_son_unicos() -> None:
    ids = [caso.id for caso in MENSAJES]

    assert len(ids) == len(set(ids))


def test_al_menos_dos_mensajes_piden_algo_fuera_del_catalogo() -> None:
    casos = [
        caso
        for caso in MENSAJES
        if any(item.review_reason == "no_reconocido" for item in caso.esperado)
    ]

    assert len(casos) >= 2


def test_al_menos_un_mensaje_es_ambiguo_entre_variantes() -> None:
    assert any(
        item.review_reason == "falta_variante" for caso in MENSAJES for item in caso.esperado
    )


def test_al_menos_un_mensaje_no_es_un_pedido() -> None:
    assert any(caso.esperado == () for caso in MENSAJES)


@pytest.mark.parametrize("caso", MENSAJES, ids=lambda caso: caso.id)
def test_cada_mensaje_esta_en_minusculas_y_sin_tildes(caso: CasoBanco) -> None:
    assert caso.texto == caso.texto.lower()
    assert not re.search("[áéíóúü]", caso.texto)


@pytest.mark.parametrize("caso", MENSAJES, ids=lambda caso: caso.id)
def test_cada_caso_declara_su_procedencia(caso: CasoBanco) -> None:
    assert caso.origen in {"E01", "E02", "inventado"}


@pytest.mark.parametrize("caso", MENSAJES, ids=lambda caso: caso.id)
def test_lo_esperado_existe_en_el_catalogo_de_su_negocio(caso: CasoBanco) -> None:
    catalogo = CATALOGOS[caso.negocio]
    cotizables = {(item.product_id, item.variant_id) for item in catalogo}
    productos = {item.product_id for item in catalogo}

    for item in caso.esperado:
        if item.status == "lista":
            assert (item.product_id, item.variant_id) in cotizables
        elif item.product_id is not None:
            assert item.product_id in productos


# Puntuación


def _linea(
    product_id: int | None,
    variant_id: int | None,
    quantity: int | None,
    status: str = "lista",
    review_reason: str | None = None,
) -> Any:
    lista = status == "lista"
    return quotes.LineDraft(
        customer_text="texto del cliente",
        product_id=product_id,
        variant_id=variant_id,
        quantity=quantity,
        quantity_assumed=False,
        status=LineStatus(status),
        review_reason=ReviewReason(review_reason) if review_reason else None,
        label="Etiqueta" if lista else None,
        unit_price=1000 if lista else None,
    )


TORTA = ItemEsperado(1, 102, 2)
ALFAJORES = ItemEsperado(5, None, 12)
FUERA = ItemEsperado(None, None, None, "por_revisar", "no_reconocido")


def test_lineas_identicas_a_lo_esperado_dan_acierto_completo() -> None:
    acierto = puntuar((TORTA, ALFAJORES), [_linea(1, 102, 2), _linea(5, None, 12)])

    assert acierto == Acierto(esperados=2, correctos=2, sobrantes=0)
    assert acierto.valor == 1.0


def test_una_cantidad_equivocada_no_cuenta_y_su_linea_sobra() -> None:
    acierto = puntuar((TORTA, ALFAJORES), [_linea(1, 102, 3), _linea(5, None, 12)])

    assert acierto == Acierto(esperados=2, correctos=1, sobrantes=1)
    assert acierto.valor == pytest.approx(1 / 3)


def test_una_linea_de_mas_cuenta_como_sobrante() -> None:
    acierto = puntuar((TORTA,), [_linea(1, 102, 2), _linea(7, None, 1)])

    assert acierto == Acierto(esperados=1, correctos=1, sobrantes=1)
    assert acierto.valor == 0.5


def test_un_producto_inventado_no_acierta_un_no_reconocido() -> None:
    acierto = puntuar((FUERA,), [_linea(999, None, 1)])

    assert acierto == Acierto(esperados=1, correctos=0, sobrantes=1)


def test_un_no_reconocido_se_acierta_con_una_linea_por_revisar_sin_producto() -> None:
    linea = _linea(None, None, 12, status="por_revisar", review_reason="no_reconocido")

    assert puntuar((FUERA,), [linea]) == Acierto(esperados=1, correctos=1, sobrantes=0)


def test_el_estado_cuenta_una_linea_por_revisar_no_acierta_una_lista() -> None:
    linea = _linea(1, None, 2, status="por_revisar", review_reason="falta_variante")

    assert puntuar((TORTA,), [linea]) == Acierto(esperados=1, correctos=0, sobrantes=1)


def test_con_cantidad_esperada_none_cualquier_cantidad_es_correcta() -> None:
    collar = ItemEsperado(22, None, None, "por_revisar", "falta_variante")
    linea = _linea(22, None, 1, status="por_revisar", review_reason="falta_variante")

    assert puntuar((collar,), [linea]) == Acierto(esperados=1, correctos=1, sobrantes=0)


def test_cada_linea_acierta_un_solo_item_esperado() -> None:
    acierto = puntuar((TORTA, TORTA), [_linea(1, 102, 2)])

    assert acierto == Acierto(esperados=2, correctos=1, sobrantes=0)


def test_caso_limite_sin_esperados_ni_lineas_el_acierto_es_1() -> None:
    acierto = puntuar((), [])

    assert acierto == Acierto(esperados=0, correctos=0, sobrantes=0)
    assert acierto.valor == 1.0


def test_caso_limite_sin_esperados_y_con_una_linea_el_acierto_es_0() -> None:
    acierto = puntuar((), [_linea(1, 102, 1)])

    assert acierto == Acierto(esperados=0, correctos=0, sobrantes=1)
    assert acierto.valor == 0.0
