"""Servicio de cotización: `quote_message`, totales y lista (contracts/quote-service.md).

El modelo es siempre un `FunctionModel` (constitución II). Los precios esperados salen del
catálogo de referencia, nunca de la extracción simulada, que no puede traerlos (principio V).
"""

import asyncio
import datetime

import pytest
from sqlmodel import Session

from app.models.catalog import Product, ProductVariant
from app.models.quote import AiOutcome, LineStatus, Quote, QuoteStatus, ReviewReason
from app.services import quotes
from tests.banco_mensajes import MENSAJES
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    line_payload,
    quote_agent,
    seed_reference_catalog,
)

TODAY = datetime.date(2026, 11, 18)  # miércoles
NOW = datetime.datetime(2026, 11, 18, 20, 0, tzinfo=datetime.UTC)


@pytest.fixture
def ref(session: Session) -> ReferenceCatalog:
    return seed_reference_catalog(session)


def _quote(
    session: Session,
    message: str,
    model: ScriptedModel,
    *,
    now: datetime.datetime = NOW,
) -> Quote:
    return asyncio.run(
        quotes.quote_message(
            session,
            message,
            extractor=quote_agent(model),
            timeout_seconds=10,
            today=TODAY,
            now=now,
        )
    )


def _model(*lines: dict[str, object], **delivery: object) -> ScriptedModel:
    return extraction_model({**EMPTY_EXTRACTION, **delivery, "lines": list(lines)})


def _two_products(ref: ReferenceCatalog) -> ScriptedModel:
    return _model(
        line_payload(ref.torta_id, ref.mediana_id, 2, "dos tortas medianas"),
        line_payload(ref.cafe_id, None, 1, "un cafe"),
    )


def _naive(value: datetime.datetime) -> datetime.datetime:
    # SQLite no guarda la zona horaria; PostgreSQL sí. Se compara el instante en UTC.
    if value.tzinfo is None:
        return value
    return value.astimezone(datetime.UTC).replace(tzinfo=None)


# Camino feliz


def test_un_mensaje_con_dos_productos_queda_guardado_como_borrador(
    session: Session, ref: ReferenceCatalog
) -> None:
    quote = _quote(session, "  dos tortas medianas y un cafe  ", _two_products(ref))

    assert quote.id is not None
    assert quote.status == QuoteStatus.BORRADOR
    assert quote.ai_outcome == AiOutcome.OK
    assert quote.ai_duration_ms is not None
    assert quote.ai_duration_ms >= 0
    assert quote.customer_message == "dos tortas medianas y un cafe"
    assert _naive(quote.created_at) == NOW.replace(tzinfo=None)
    assert [line.position for line in quote.lines] == [1, 2]
    assert all(line.status == LineStatus.LISTA for line in quote.lines)
    assert quotes.pending_count(quote) == 0


def test_la_cotizacion_guardada_se_puede_volver_a_leer(
    session: Session, ref: ReferenceCatalog
) -> None:
    quote = _quote(session, "dos tortas medianas y un cafe", _two_products(ref))
    assert quote.id is not None

    stored = quotes.get_quote(session, quote.id)

    assert [line.label for line in stored.lines] == [
        "Torta de chocolate — Tamaño: Mediana",
        "Café",
    ]


def test_una_cotizacion_inexistente_no_se_encuentra(session: Session) -> None:
    with pytest.raises(quotes.QuoteNotFoundError):
        quotes.get_quote(session, 999)


# Precios y totales (SC-003): del catálogo y en enteros


def test_los_precios_salen_del_catalogo_y_el_total_es_un_entero(
    session: Session, ref: ReferenceCatalog
) -> None:
    quote = _quote(session, "dos tortas medianas y un cafe", _two_products(ref))

    assert [line.unit_price for line in quote.lines] == [45000, 3500]
    total = quotes.quote_total(quote)
    assert total == 45000 * 2 + 3500 * 1 == 93500
    assert type(total) is int


def test_r10_el_precio_del_mensaje_no_llega_a_la_linea_ni_el_del_catalogo_a_la_ia(
    session: Session, ref: ReferenceCatalog
) -> None:
    caso = next(caso for caso in MENSAJES if caso.id == "R10")  # «estaba en 40 mil»
    model = _model(line_payload(ref.torta_id, ref.mediana_id, 1, caso.texto))

    quote = _quote(session, caso.texto, model)

    (line,) = quote.lines
    assert line.unit_price == 45000
    assert quotes.quote_total(quote) == 45000
    # La IA ve el mensaje tal cual, pero nunca los precios del catálogo.
    assert "40 mil" in model.user_prompt
    assert "45000" not in model.user_prompt
    assert "45.000" not in model.user_prompt


def test_la_ia_recibe_el_catalogo_vigente_con_sus_ids(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _two_products(ref)

    _quote(session, "dos tortas medianas y un cafe", model)

    prompt = model.user_prompt
    for identifier in (ref.torta_id, ref.mediana_id, ref.grande_id, ref.cafe_id):
        assert str(identifier) in prompt
    assert "Torta de chocolate" in prompt
    assert "Café" in prompt


# Entrega


def test_la_entrega_se_extrae_y_la_fecha_y_la_hora_las_convierte_el_codigo(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(
        line_payload(ref.cafe_id, None, 1),
        delivery_date={"kind": "weekday", "weekday": 5},
        delivery_time="a las 3 de la tarde",
        delivery_mode="recoger",
    )

    quote = _quote(session, "un cafe para recoger el sabado a las 3 de la tarde", model)

    assert quote.delivery_date == datetime.date(2026, 11, 21)
    assert quote.delivery_date_needs_review is False
    assert quote.delivery_time == datetime.time(15, 0)
    assert quote.delivery_time_needs_review is False
    assert quote.delivery_mode == "recoger"


def test_una_hora_sin_manana_ni_tarde_se_toma_como_tarde_y_se_marca(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(line_payload(ref.cafe_id, None, 1), delivery_time="a las 3")

    quote = _quote(session, "un cafe a las 3", model)

    assert quote.delivery_time == datetime.time(15, 0)
    assert quote.delivery_time_needs_review is True


def test_una_hora_mal_escrita_no_manda_la_cotizacion_al_camino_manual(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(line_payload(ref.cafe_id, None, 1), delivery_time="9:00")

    quote = _quote(session, "un cafe a las 9:00", model)

    assert quote.ai_outcome == AiOutcome.OK
    assert len(quote.lines) == 1
    assert quote.delivery_time == datetime.time(9, 0)


def test_la_direccion_a_domicilio_se_guarda(session: Session, ref: ReferenceCatalog) -> None:
    model = _model(
        line_payload(ref.cafe_id, None, 1),
        delivery_mode="domicilio",
        delivery_address="Calle 10 # 5-20",
    )

    quote = _quote(session, "un cafe a domicilio en la calle 10 # 5-20", model)

    assert quote.delivery_mode == "domicilio"
    assert quote.delivery_address == "Calle 10 # 5-20"
    assert quote.delivery_mode_needs_review is False


def test_sin_datos_de_entrega_todo_queda_vacio_y_sin_marcas(
    session: Session, ref: ReferenceCatalog
) -> None:
    quote = _quote(session, "un cafe", _model(line_payload(ref.cafe_id, None, 1)))

    assert quote.delivery_date is None
    assert quote.delivery_time is None
    assert quote.delivery_mode is None
    assert quote.delivery_address is None
    assert not quote.delivery_date_needs_review
    assert not quote.delivery_time_needs_review
    assert not quote.delivery_mode_needs_review


# Errores de dominio: se lanzan antes de llamar a la IA


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
def test_un_mensaje_vacio_se_rechaza_sin_llamar_a_la_ia(
    session: Session, ref: ReferenceCatalog, message: str
) -> None:
    model = _two_products(ref)

    with pytest.raises(quotes.EmptyMessageError):
        _quote(session, message, model)

    assert model.calls == 0


def test_un_mensaje_de_mas_de_2000_caracteres_se_rechaza_sin_llamar_a_la_ia(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _two_products(ref)

    with pytest.raises(quotes.MessageTooLongError):
        _quote(session, "x" * 2001, model)

    assert model.calls == 0


def test_un_mensaje_de_2000_caracteres_se_cotiza(session: Session, ref: ReferenceCatalog) -> None:
    model = _two_products(ref)

    _quote(session, "x" * 2000, model)

    assert model.calls == 1


def test_sin_nada_cotizable_se_rechaza_sin_llamar_a_la_ia(session: Session) -> None:
    model = _model()

    with pytest.raises(quotes.NothingToQuoteError):
        _quote(session, "una torta", model)

    assert model.calls == 0


# Lista


def test_la_lista_va_de_la_cotizacion_mas_reciente_a_la_mas_antigua(
    session: Session, ref: ReferenceCatalog
) -> None:
    first = _quote(session, "un cafe", _model(line_payload(ref.cafe_id, None, 1)))
    second = _quote(
        session,
        "otro cafe",
        _model(line_payload(ref.cafe_id, None, 1)),
        now=NOW + datetime.timedelta(minutes=5),
    )

    assert [quote.id for quote in quotes.list_quotes(session)] == [second.id, first.id]


# Historia 2: lo que queda por revisar


def test_un_valido_un_inexistente_y_uno_sin_variante_solo_suma_el_valido(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(
        line_payload(ref.cafe_id, None, 2, "dos cafes"),
        line_payload(9999, None, 12, "una docena de empanadas"),
        line_payload(ref.torta_id, None, 1, "una torta de chocolate"),
    )

    quote = _quote(session, "dos cafes, una docena de empanadas y una torta de chocolate", model)

    assert [
        (line.customer_text, line.status, line.review_reason, line.product_id, line.unit_price)
        for line in quote.lines
    ] == [
        ("dos cafes", LineStatus.LISTA, None, ref.cafe_id, 3500),
        ("una docena de empanadas", "por_revisar", ReviewReason.NO_RECONOCIDO, None, None),
        ("una torta de chocolate", "por_revisar", ReviewReason.FALTA_VARIANTE, ref.torta_id, None),
    ]
    assert quote.ai_outcome == AiOutcome.OK
    assert quotes.pending_count(quote) == 2
    assert quotes.quote_total(quote) == 7000


def test_lo_guardado_por_revisar_no_viola_llaves_foraneas(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(
        line_payload(9999, None, 1, "algo inventado"),
        line_payload(ref.torta_id, 9999, 1, "una variante inventada"),
    )

    quote = _quote(session, "algo inventado", model)

    assert quotes.pending_count(quote) == 2
    # SQLite no aplica las FK al guardar y PostgreSQL sí: se le pide a SQLite que las revise.
    assert session.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_si_no_se_reconoce_nada_se_guarda_el_borrador_con_total_0(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(
        line_payload(None, None, 15, "gorras bordadas"),
        line_payload(None, None, None, "una empanada"),
    )

    quote = _quote(session, "gorras bordadas y una empanada", model)

    assert quote.id is not None
    assert quote.status == QuoteStatus.BORRADOR
    assert all(line.status == LineStatus.POR_REVISAR for line in quote.lines)
    assert quotes.pending_count(quote) == 2
    assert quotes.quote_total(quote) == 0


def test_un_producto_y_una_variante_desactivados_no_reciben_precio(
    session: Session, ref: ReferenceCatalog
) -> None:
    cafe = session.get(Product, ref.cafe_id)
    grande = session.get(ProductVariant, ref.grande_id)
    assert cafe is not None
    assert grande is not None
    cafe.is_active = grande.is_active = False
    session.add_all([cafe, grande])
    session.commit()
    model = _model(
        line_payload(ref.cafe_id, None, 1, "un cafe"),
        line_payload(ref.torta_id, ref.grande_id, 1, "una torta grande"),
    )

    quote = _quote(session, "un cafe y una torta grande", model)

    assert [(line.review_reason, line.product_id, line.unit_price) for line in quote.lines] == [
        (ReviewReason.NO_RECONOCIDO, None, None),
        (ReviewReason.NO_RECONOCIDO, None, None),
    ]


@pytest.mark.parametrize("quantity", [0, 1000])
def test_una_cantidad_fuera_de_rango_se_guarda_por_revisar_sin_fallar(
    session: Session, ref: ReferenceCatalog, quantity: int
) -> None:
    quote = _quote(session, "muchos cafes", _model(line_payload(ref.cafe_id, None, quantity)))

    (line,) = quote.lines
    assert (line.review_reason, line.quantity) == (ReviewReason.CANTIDAD_INVALIDA, None)
    assert quotes.quote_total(quote) == 0


def test_r09_un_mensaje_que_no_es_un_pedido_se_guarda_sin_lineas_ni_pendientes(
    session: Session, ref: ReferenceCatalog
) -> None:
    caso = next(caso for caso in MENSAJES if caso.id == "R09")

    quote = _quote(session, caso.texto, _model())

    assert quote.ai_outcome == AiOutcome.OK
    assert quote.lines == []
    assert quotes.pending_count(quote) == 0
    assert quotes.quote_total(quote) == 0


def test_una_fecha_que_no_se_puede_resolver_queda_vacia_y_marcada(
    session: Session, ref: ReferenceCatalog
) -> None:
    message = "un cafe a fin de mes, si se puede"
    model = _model(line_payload(ref.cafe_id, None, 1), delivery_date={"kind": "unknown"})

    quote = _quote(session, message, model)

    assert quote.delivery_date is None
    assert quote.delivery_date_needs_review is True
    assert quote.customer_message == message


def test_una_direccion_sin_modalidad_asume_domicilio_y_lo_marca(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(line_payload(ref.cafe_id, None, 1), delivery_address="Calle 10 # 5-20")

    quote = _quote(session, "un cafe para la calle 10 # 5-20", model)

    assert quote.delivery_mode == "domicilio"
    assert quote.delivery_mode_needs_review is True


def test_una_direccion_vacia_no_asume_domicilio(session: Session, ref: ReferenceCatalog) -> None:
    model = _model(line_payload(ref.cafe_id, None, 1), delivery_address="")

    quote = _quote(session, "un cafe", model)

    assert quote.delivery_mode is None
    assert quote.delivery_mode_needs_review is False


def test_una_direccion_con_recoger_respeta_lo_que_dijo_el_cliente(
    session: Session, ref: ReferenceCatalog
) -> None:
    model = _model(
        line_payload(ref.cafe_id, None, 1),
        delivery_mode="recoger",
        delivery_address="Calle 10 # 5-20",
    )

    quote = _quote(session, "un cafe, lo recojo", model)

    assert quote.delivery_mode == "recoger"
    assert quote.delivery_mode_needs_review is False
