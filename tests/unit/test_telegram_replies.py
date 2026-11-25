"""Textos del bot de Telegram (specs/005-bot-telegram/spec.md, escenarios 5, 6 y 14)."""

import datetime
from typing import Any

import pytest

from app.models.catalog import QuotableItem
from app.models.quote import AiOutcome, LineStatus, Quote, QuoteLine, ReviewReason
from app.services.telegram_replies import (
    TELEGRAM_MAX_LENGTH,
    catalog_text,
    owner_notice,
    quote_reply,
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


# Fase 3: la respuesta a una cotización (escenarios 7 a 10) y el aviso al dueño (D7)

QUOTE_ID = 4242  # un número que no aparece en ningún precio ni cantidad
BASE_URL = "https://pedidofacil.example"
LINK = f"{BASE_URL}/cotizaciones/{QUOTE_ID}"
DONE = "El dueño te confirmará el pedido."
REVIEW = "Recibimos tu pedido; el dueño lo revisará y te escribirá."
# FR-03: nada interno en un mensaje al cliente.
INTERNAL = (str(QUOTE_ID), "gemini", "timeout", "provider_error", "invalid_output", "Error", "503")


def _line(**fields: Any) -> QuoteLine:
    return QuoteLine(**fields)


def _ready(
    label: str, price: int, quantity: int, product_id: int, variant_id: int | None
) -> QuoteLine:
    return _line(
        position=1,
        status=LineStatus.LISTA,
        product_id=product_id,
        variant_id=variant_id,
        label=label,
        unit_price=price,
        quantity=quantity,
        customer_text="texto del cliente",
    )


def _pending(text: str, reason: ReviewReason, product_id: int | None = None) -> QuoteLine:
    return _line(
        position=1,
        status=LineStatus.POR_REVISAR,
        review_reason=reason,
        customer_text=text,
        product_id=product_id,
    )


def _quote(*lines: QuoteLine, outcome: AiOutcome = AiOutcome.OK) -> Quote:
    return Quote(
        id=QUOTE_ID,
        customer_message="mensaje del cliente",
        created_at=datetime.datetime(2026, 11, 24, 15, tzinfo=datetime.UTC),
        ai_outcome=outcome,
        lines=list(lines),
    )


TORTA_MEDIANA = ("Torta de chocolate — Tamaño: Mediana", 45000, 2, 1, 102)
ALFAJORES = ("Alfajor", 2500, 12, 5, None)


def test_una_cotizacion_reconocida_trae_cada_linea_el_total_y_el_cierre() -> None:
    text = quote_reply(_quote(_ready(*TORTA_MEDIANA), _ready(*ALFAJORES)), REPOSTERIA)

    torta = _line_with(text, "Torta de chocolate — Tamaño: Mediana")
    assert "2" in torta
    assert "$ 90.000" in torta  # 45.000 por 2
    alfajores = _line_with(text, "Alfajor")
    assert "12" in alfajores
    assert "$ 30.000" in alfajores
    assert "$ 120.000" in _line_with(text, "Total")
    assert text.rstrip().endswith(DONE)


def test_las_pendientes_citan_al_cliente_y_el_total_solo_suma_las_reconocidas() -> None:
    quote = _quote(
        _ready(*TORTA_MEDIANA),
        _pending("una docena de empanadas", ReviewReason.NO_RECONOCIDO),
        _pending("una torta de zanahoria", ReviewReason.FALTA_VARIANTE, product_id=2),
        _pending("cero alfajores", ReviewReason.CANTIDAD_INVALIDA, product_id=5),
    )

    text = quote_reply(quote, REPOSTERIA)

    assert "$ 90.000" in _line_with(text, "Total")
    assert "no lo encontré" in _line_with(text, "una docena de empanadas")
    assert "la cantidad no es válida" in _line_with(text, "cero alfajores")
    presentation = text.partition("una torta de zanahoria")[2]
    assert "¿qué presentación?" in presentation.splitlines()[0]
    # Las presentaciones de ese producto, y no las de otro.
    assert "Mediana" in presentation
    assert "Grande" in presentation
    assert "Pequeña" not in presentation  # solo la torta de chocolate la tiene
    assert DONE in text


def test_si_nada_se_reconocio_envia_el_catalogo_sin_total() -> None:
    quote = _quote(
        _pending("unas empanadas", ReviewReason.NO_RECONOCIDO),
        _pending("un tamal", ReviewReason.NO_RECONOCIDO),
    )

    text = quote_reply(quote, REPOSTERIA)

    assert "no lo encontré" in _line_with(text, "unas empanadas")
    assert catalog_text(REPOSTERIA) in text
    assert "Total" not in text


def test_un_mensaje_sin_pedido_explica_como_pedir() -> None:
    text = quote_reply(_quote(), REPOSTERIA)

    assert "/catalogo" in text
    assert "Total" not in text
    assert "$" not in text


@pytest.mark.parametrize(
    "outcome",
    [AiOutcome.TIMEOUT, AiOutcome.PROVIDER_ERROR, AiOutcome.INVALID_OUTPUT, AiOutcome.DISABLED],
    ids=lambda outcome: outcome.value,
)
def test_si_la_ia_no_respondio_bien_el_duenio_lo_revisara(outcome: AiOutcome) -> None:
    text = quote_reply(_quote(outcome=outcome), REPOSTERIA)

    assert text == REVIEW


CASES = {
    "reconocida": _quote(_ready(*TORTA_MEDIANA)),
    "pendientes": _quote(_ready(*TORTA_MEDIANA), _pending("empanadas", ReviewReason.NO_RECONOCIDO)),
    "nada_reconocido": _quote(_pending("empanadas", ReviewReason.NO_RECONOCIDO)),
    "sin_pedido": _quote(),
    "ia_caida": _quote(outcome=AiOutcome.PROVIDER_ERROR),
}


@pytest.mark.parametrize("quote", CASES.values(), ids=CASES.keys())
def test_ningun_mensaje_al_cliente_lleva_informacion_interna(quote: Quote) -> None:
    text = quote_reply(quote, REPOSTERIA)

    for internal in INTERNAL:
        assert internal not in text


@pytest.mark.parametrize(
    "quote",
    [CASES["pendientes"], CASES["nada_reconocido"], CASES["ia_caida"]],
    ids=["pendientes", "nada_reconocido", "ia_caida"],
)
def test_el_duenio_recibe_aviso_con_el_numero_y_el_enlace(quote: Quote) -> None:
    notice = owner_notice(quote, BASE_URL)

    assert notice is not None
    assert f"n.º {QUOTE_ID}" in notice
    assert LINK in notice


@pytest.mark.parametrize(
    "quote", [CASES["reconocida"], CASES["sin_pedido"]], ids=["reconocida", "sin_pedido"]
)
def test_sin_nada_que_revisar_el_duenio_no_recibe_aviso(quote: Quote) -> None:
    assert owner_notice(quote, BASE_URL) is None
