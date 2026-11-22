"""Fechas y horas de entrega: las convierte el código, no la IA (research R7 y R7b, SC-005).

`resolve_delivery_date` recibe el día actual como parámetro y no lee el reloj. Una prueba lo
demuestra con time-machine: con el reloj en otra fecha, el resultado no cambia. Que el día
actual sea el de Colombia se prueba en las páginas (tests/integration/test_quote_pages.py).
"""

import datetime

import pytest
import time_machine

from app.services.quote_ai import DateExpression, resolve_delivery_date, resolve_delivery_time

# Miércoles 18 de noviembre de 2026.
TODAY = datetime.date(2026, 11, 18)


def _date(**fields: object) -> DateExpression:
    return DateExpression.model_validate(fields)


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ({"kind": "today"}, (datetime.date(2026, 11, 18), False)),
        ({"kind": "offset", "days": 0}, (datetime.date(2026, 11, 18), False)),
        ({"kind": "offset", "days": 1}, (datetime.date(2026, 11, 19), False)),  # mañana
        ({"kind": "offset", "days": 2}, (datetime.date(2026, 11, 20), False)),  # pasado mañana
        ({"kind": "weekday", "weekday": 5}, (datetime.date(2026, 11, 21), False)),  # el sábado
        ({"kind": "weekday", "weekday": 0}, (datetime.date(2026, 11, 23), False)),  # el lunes
        ({"kind": "weekday", "weekday": 2}, (datetime.date(2026, 11, 18), True)),  # hoy: marcar
        ({"kind": "day_of_month", "day": 25}, (datetime.date(2026, 11, 25), False)),
        ({"kind": "day_of_month", "day": 10}, (datetime.date(2026, 12, 10), False)),  # ya pasó
        ({"kind": "day_of_month", "day": 31}, (None, True)),  # noviembre no tiene 31
        ({"kind": "absolute", "date": "2026-11-28"}, (datetime.date(2026, 11, 28), False)),
        ({"kind": "absolute", "date": "2026-11-01"}, (datetime.date(2026, 11, 1), True)),  # pasada
        ({"kind": "unknown"}, (None, True)),  # «a fin de mes, si se puede»
    ],
)
def test_cada_expresion_de_fecha_se_convierte_respecto_al_dia_dado(
    expr: dict[str, object], expected: tuple[datetime.date | None, bool]
) -> None:
    assert resolve_delivery_date(_date(**expr), TODAY) == expected


def test_sin_fecha_mencionada_no_hay_fecha_ni_marca() -> None:
    assert resolve_delivery_date(None, TODAY) == (None, False)


def test_la_conversion_no_depende_del_dia_en_que_corren_las_pruebas() -> None:
    sabado = _date(kind="weekday", weekday=5)

    with time_machine.travel(datetime.datetime(2031, 2, 3, 12, tzinfo=datetime.UTC), tick=False):
        result = resolve_delivery_date(sabado, TODAY)

    assert result == (datetime.date(2026, 11, 21), False)


# Hora (research R7b)


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("15:00", (datetime.time(15, 0), False)),
        ("3 de la tarde", (datetime.time(15, 0), False)),
        ("a las 3 de la tarde", (datetime.time(15, 0), False)),
        ("3 pm", (datetime.time(15, 0), False)),
        ("9:00", (datetime.time(9, 0), False)),
        ("9", (datetime.time(9, 0), False)),
        ("9 de la mañana", (datetime.time(9, 0), False)),
        ("10 am", (datetime.time(10, 0), False)),
        ("7:30 pm", (datetime.time(19, 30), False)),
        ("mediodia", (datetime.time(12, 0), False)),
        ("a las 3", (datetime.time(15, 0), True)),  # sin mañana ni tarde: tarde, y se marca
        ("en la tarde", (None, True)),
        ("25:00", (None, True)),
    ],
)
def test_cada_expresion_de_hora_se_normaliza(
    expr: str, expected: tuple[datetime.time | None, bool]
) -> None:
    assert resolve_delivery_time(expr) == expected


def test_sin_hora_mencionada_no_hay_hora_ni_marca() -> None:
    assert resolve_delivery_time(None) == (None, False)


# «De la noche» no es «de la tarde»: las 12 y las primeras horas son de la madrugada.
@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("12 de la noche", (datetime.time(0, 0), False)),
        ("a las 12:30 de la noche", (datetime.time(0, 30), False)),
        ("1 de la noche", (datetime.time(1, 0), False)),
        ("a la 1 de la noche", (datetime.time(1, 0), False)),
        ("4 de la noche", (datetime.time(4, 0), False)),
        ("5 de la noche", (datetime.time(17, 0), True)),  # madrugada o tarde: se marca
        # Guardas: lo que el arreglo no debe romper.
        ("6 de la noche", (datetime.time(18, 0), False)),
        ("11 de la noche", (datetime.time(23, 0), False)),
        ("12 pm", (datetime.time(12, 0), False)),
        ("1 pm", (datetime.time(13, 0), False)),
        ("12 de la tarde", (datetime.time(12, 0), False)),
        ("1 de la tarde", (datetime.time(13, 0), False)),
    ],
)
def test_de_la_noche_distingue_la_madrugada_de_la_noche(
    expr: str, expected: tuple[datetime.time | None, bool]
) -> None:
    assert resolve_delivery_time(expr) == expected
