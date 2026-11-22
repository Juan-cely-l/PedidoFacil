"""Plantillas: formato de pesos y plantilla base."""

import datetime

import pytest

from app.templating import colombia, cop, templates


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (1, "$ 1"),
        (5000, "$ 5.000"),
        (45000, "$ 45.000"),
        (1250000, "$ 1.250.000"),
        (100_000_000, "$ 100.000.000"),
    ],
)
def test_cop_formatea_pesos_con_punto_de_miles(amount: int, expected: str) -> None:
    assert cop(amount) == expected


def test_cop_esta_registrado_como_filtro() -> None:
    assert templates.env.filters["cop"] is cop


def test_plantilla_base_es_movil_en_espanol_y_carga_pico_con_version_fija() -> None:
    html = templates.get_template("base.html").render()

    assert '<html lang="es"' in html
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "@picocss/pico@2." in html
    assert 'integrity="sha384-' in html
    assert 'href="/productos"' in html


# Cobertura de una rama existente de `colombia`, no comportamiento nuevo: es la que corre en
# producción. PostgreSQL devuelve fechas con zona; SQLite, la base de las pruebas, sin ella.


@pytest.mark.parametrize(
    "moment",
    [
        datetime.datetime(2026, 11, 21, 3, 30, tzinfo=datetime.UTC),
        # PostgreSQL entrega el instante en la zona de la conexión, que no tiene que ser UTC. Con
        # solo el caso UTC, un filtro que pisara la zona con `replace(tzinfo=UTC)` pasaría.
        datetime.datetime(
            2026, 11, 20, 22, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
        ),
        datetime.datetime(
            2026, 11, 21, 5, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
        ),
    ],
    ids=["utc", "bogota", "utc+2"],
)
def test_colombia_convierte_una_fecha_que_ya_trae_zona_horaria(moment: datetime.datetime) -> None:
    assert colombia(moment) == "20/11/2026 22:30"
