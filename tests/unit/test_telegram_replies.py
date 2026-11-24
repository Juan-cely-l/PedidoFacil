"""Textos del bot de Telegram (specs/005-bot-telegram/spec.md, escenarios 5, 6 y 14)."""

import pytest

from app.models.catalog import QuotableItem
from app.services.telegram_replies import (
    TELEGRAM_MAX_LENGTH,
    catalog_text,
    split_messages,
    start_text,
)
from tests.banco_mensajes import CATALOGOS

REPOSTERIA = CATALOGOS["reposteria"]


def _line_with(text: str, label: str) -> str:
    (line,) = [line for line in text.splitlines() if label in line]
    return line


def test_el_catalogo_trae_cada_item_con_su_precio_en_la_misma_linea() -> None:
    text = catalog_text(REPOSTERIA)

    assert "$ 45.000" in _line_with(text, "Torta de chocolate — Tamaño: Mediana")
    assert "$ 2.500" in _line_with(text, "Alfajor")
    for item in REPOSTERIA:
        assert item.label in text


def test_el_catalogo_conserva_el_orden_de_list_quotable_items() -> None:
    text = catalog_text(REPOSTERIA)

    positions = [text.index(item.label) for item in REPOSTERIA]
    assert positions == sorted(positions)


def test_sin_catalogo_dice_que_no_hay_productos() -> None:
    assert catalog_text([]) == "Todavía no hay productos disponibles."


def test_el_saludo_explica_que_escribir_y_menciona_el_catalogo() -> None:
    text = start_text()

    assert "/catalogo" in text
    assert "$" not in text  # el saludo no trae precios


def _items(count: int) -> list[QuotableItem]:
    return [
        QuotableItem(
            product_id=n, variant_id=None, label=f"Producto número {n:04d}", unit_price=1000
        )
        for n in range(1, count + 1)
    ]


def test_un_catalogo_largo_se_parte_sin_cortar_ninguna_linea() -> None:
    text = catalog_text(_items(300))
    assert len(text) > TELEGRAM_MAX_LENGTH

    parts = split_messages(text)

    assert len(parts) > 1
    assert all(len(part) <= TELEGRAM_MAX_LENGTH for part in parts)
    # Juntar las partes devuelve el texto completo, línea por línea.
    assert "\n".join(parts).splitlines() == text.splitlines()


def test_un_texto_corto_queda_en_un_solo_mensaje() -> None:
    assert split_messages("hola\nmundo") == ["hola\nmundo"]


@pytest.mark.parametrize("limit", [10, 25])
def test_partir_respeta_cualquier_limite(limit: int) -> None:
    text = "\n".join(f"línea {n}" for n in range(30))

    parts = split_messages(text, limit=limit)

    assert all(len(part) <= limit for part in parts)
    assert "\n".join(parts).splitlines() == text.splitlines()


def test_una_linea_mas_larga_que_el_limite_se_corta_sin_perder_texto() -> None:
    text = "x" * 25

    parts = split_messages(text, limit=10)

    assert parts == ["x" * 10, "x" * 10, "x" * 5]
