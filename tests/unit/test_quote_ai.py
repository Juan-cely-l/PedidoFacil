"""Pruebas del contrato con la IA (app/services/quote_ai.py).

El esquema de salida no tiene ningún campo de precio y rechaza campos de más: aunque el modelo
quiera fijar un precio, la salida no valida (principio V, RD-2, research R5).
"""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.services import quote_ai

PRICE_WORDS = ("price", "subtotal", "total", "precio")


def _line(**overrides: object) -> dict[str, object]:
    line: dict[str, object] = {
        "customer_text": "dos tortas de chocolate medianas",
        "product_id": 1,
        "variant_id": 102,
        "quantity": 2,
    }
    line.update(overrides)
    return line


def _extraction(**overrides: object) -> dict[str, object]:
    extraction: dict[str, object] = {
        "lines": [_line()],
        "delivery_date": {"kind": "weekday", "weekday": 5},
        "delivery_time": "a las 3 de la tarde",
        "delivery_mode": "recoger",
        "delivery_address": None,
    }
    extraction.update(overrides)
    return extraction


def _validate(payload: dict[str, object]) -> Any:
    return quote_ai.QuoteExtraction.model_validate(payload)


def _schema_models() -> list[type[BaseModel]]:
    return [
        quote_ai.QuoteExtraction,
        quote_ai.ExtractedLine,
        quote_ai.DateExpression,
    ]


# Sin precios (RD-2)


def test_ningun_modelo_de_la_salida_tiene_campos_de_precio() -> None:
    for model in _schema_models():
        for field_name in model.model_fields:
            assert not any(word in field_name.lower() for word in PRICE_WORDS), (
                f"{model.__name__}.{field_name} parece un precio"
            )


def test_una_extraccion_valida_se_acepta() -> None:
    extraction = _validate(_extraction())

    assert extraction.lines[0].product_id == 1
    assert extraction.lines[0].quantity == 2


def test_un_precio_en_una_linea_hace_fallar_la_validacion() -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(lines=[_line(price=100)]))


def test_un_total_en_la_extraccion_hace_fallar_la_validacion() -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(total=45000))


def test_un_campo_de_mas_en_la_fecha_hace_fallar_la_validacion() -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(delivery_date={"kind": "today", "price": 0}))


# Límites del esquema (data-model.md «Salida de la IA»)


def test_se_aceptan_hasta_30_lineas() -> None:
    extraction = _validate(_extraction(lines=[_line()] * 30))

    assert len(extraction.lines) == 30


def test_mas_de_30_lineas_se_rechazan() -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(lines=[_line()] * 31))


@pytest.mark.parametrize("customer_text", ["", "x" * 201])
def test_el_texto_del_cliente_va_de_1_a_200_caracteres(customer_text: str) -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(lines=[_line(customer_text=customer_text)]))


def test_la_direccion_tiene_maximo_200_caracteres() -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(delivery_address="x" * 201))


# La hora es la expresión que vio la IA, sin formato: la normaliza el código (research R7b).


@pytest.mark.parametrize(
    "delivery_time", ["9:00", "15:00", "3pm", "a las 3 de la tarde", "mediodia", "25:00", None]
)
def test_la_hora_se_acepta_como_la_expresion_que_vio_la_ia(delivery_time: str | None) -> None:
    extraction = _validate(_extraction(delivery_time=delivery_time))

    assert extraction.delivery_time == delivery_time


def test_una_hora_mal_escrita_no_invalida_las_lineas() -> None:
    # Con un formato estricto, «9:00» tumbaba toda la extracción y mandaba al camino manual una
    # cotización con líneas correctas.
    extraction = _validate(_extraction(delivery_time="9:00"))

    assert [line.product_id for line in extraction.lines] == [1]


@pytest.mark.parametrize("delivery_time", ["", "x" * 41])
def test_la_expresion_de_hora_va_de_1_a_40_caracteres(delivery_time: str) -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(delivery_time=delivery_time))


@pytest.mark.parametrize("delivery_mode", ["domicilio", "recoger", None])
def test_la_modalidad_es_domicilio_recoger_o_nada(delivery_mode: str | None) -> None:
    extraction = _validate(_extraction(delivery_mode=delivery_mode))

    assert extraction.delivery_mode == delivery_mode


def test_otra_modalidad_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(delivery_mode="envio"))


@pytest.mark.parametrize(
    "delivery_date",
    [
        {"kind": "next_week"},
        {"kind": "offset", "days": -1},
        {"kind": "offset", "days": 61},
        {"kind": "weekday", "weekday": 7},
        {"kind": "day_of_month", "day": 0},
        {"kind": "day_of_month", "day": 32},
        {"kind": "absolute", "date": "2026-13-01"},
    ],
)
def test_expresiones_de_fecha_fuera_de_rango_se_rechazan(delivery_date: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _validate(_extraction(delivery_date=delivery_date))


@pytest.mark.parametrize(
    "delivery_date",
    [
        {"kind": "today"},
        {"kind": "offset", "days": 0},
        {"kind": "offset", "days": 60},
        {"kind": "weekday", "weekday": 0},
        {"kind": "weekday", "weekday": 6},
        {"kind": "day_of_month", "day": 31},
        {"kind": "absolute", "date": "2026-11-28"},
        {"kind": "unknown"},
        None,
    ],
)
def test_expresiones_de_fecha_validas_se_aceptan(delivery_date: dict[str, object] | None) -> None:
    extraction = _validate(_extraction(delivery_date=delivery_date))

    assert (extraction.delivery_date is None) == (delivery_date is None)
