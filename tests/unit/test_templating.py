"""Plantillas: formato de pesos y plantilla base."""

import pytest

from app.templating import cop, templates


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
