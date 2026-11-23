"""Servicio de cotización: `quote_message`, totales y lista (contracts/quote-service.md).

El modelo es siempre un `FunctionModel` (constitución II). Los precios esperados salen del
catálogo de referencia, nunca de la extracción simulada, que no puede traerlos (principio V).
"""

import asyncio
import datetime
import time

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import (
    ContentFilterError,
    ModelAPIError,
    ModelHTTPError,
    ModelRequestTimeout,
    ModelTimeoutError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.models.fallback import FallbackModel
from sqlmodel import Session

from app.models.catalog import Product, ProductVariant
from app.models.quote import (
    AiOutcome,
    DeliveryInput,
    LineInput,
    LineStatus,
    Quote,
    QuoteStatus,
    ReviewReason,
)
from app.services import quotes
from app.services.quote_ai import QuoteExtraction
from tests.banco_mensajes import MENSAJES
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    failing_model,
    line_payload,
    quote_agent,
    raising_model,
    seed_reference_catalog,
    slow_model,
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


# Historia 3: el camino manual (research R3 y R4, SC-002)

MESSAGE = "un cafe pa mañana"


def _cotizar(
    session: Session, extractor: Agent[None, QuoteExtraction] | None, timeout: float = 10
) -> Quote:
    return asyncio.run(
        quotes.quote_message(
            session,
            MESSAGE,
            extractor=extractor,
            timeout_seconds=timeout,
            today=TODAY,
            now=NOW,
        )
    )


def _assert_manual_draft(quote: Quote, outcome: AiOutcome) -> None:
    assert quote.id is not None
    assert quote.status == QuoteStatus.BORRADOR
    assert quote.ai_outcome == outcome
    assert quote.customer_message == MESSAGE
    assert quote.lines == []
    assert quotes.quote_total(quote) == 0
    assert quote.delivery_date is None
    assert quote.delivery_time is None
    assert quote.delivery_mode is None
    assert quote.delivery_address is None


def test_si_la_ia_tarda_se_corta_a_tiempo_y_queda_el_borrador_manual(
    session: Session, ref: ReferenceCatalog
) -> None:
    started = time.monotonic()

    quote = _cotizar(session, quote_agent(slow_model(1)), timeout=0.05)

    assert time.monotonic() - started < 0.5
    _assert_manual_draft(quote, AiOutcome.TIMEOUT)
    assert quote.ai_duration_ms is not None


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModelHTTPError(503, "modelo-falso"), id="503_saturado"),
        pytest.param(ModelHTTPError(429, "modelo-falso"), id="429_cuota"),
        pytest.param(ModelHTTPError(401, "modelo-falso"), id="401_clave"),
        pytest.param(ModelAPIError("modelo-falso", "sin red"), id="red"),
        pytest.param(ModelTimeoutError("modelo-falso", "lectura"), id="lectura_http"),
        pytest.param(ModelRequestTimeout("modelo-falso", 10), id="request_timeout"),
    ],
)
def test_un_error_del_proveedor_deja_el_borrador_manual(
    session: Session, ref: ReferenceCatalog, error: Exception
) -> None:
    quote = _cotizar(session, quote_agent(raising_model(error)))

    _assert_manual_draft(quote, AiOutcome.PROVIDER_ERROR)
    assert quote.ai_duration_ms is not None


def _validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as caught:
        QuoteExtraction.model_validate({"lines": "no es una lista"})
    return caught.value


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(UnexpectedModelBehavior("respuesta rara"), id="inesperada"),
        pytest.param(ContentFilterError("filtrada"), id="filtro_de_contenido"),
        pytest.param(UsageLimitExceeded("limite"), id="otro_agent_run_error"),
        pytest.param(_validation_error(), id="validation_error"),
    ],
)
def test_una_respuesta_inutilizable_deja_el_borrador_manual(
    session: Session, ref: ReferenceCatalog, error: Exception
) -> None:
    quote = _cotizar(session, quote_agent(raising_model(error)))

    _assert_manual_draft(quote, AiOutcome.INVALID_OUTPUT)


@pytest.mark.parametrize(
    "invalid",
    [
        pytest.param({"price": 0}, id="precio_cero"),
        pytest.param({"unit_price": 1000}, id="precio_unitario"),
        pytest.param({"quantity": "muchas"}, id="tipo_invalido"),
    ],
)
def test_una_salida_invalida_no_deja_precios_ni_lineas_parciales(
    session: Session, ref: ReferenceCatalog, invalid: dict[str, object]
) -> None:
    valid_line = line_payload(ref.cafe_id, None, 1)
    model = _model(valid_line, {**line_payload(ref.torta_id, ref.mediana_id, 1), **invalid})

    quote = _cotizar(session, quote_agent(model))

    _assert_manual_draft(quote, AiOutcome.INVALID_OUTPUT)  # la línea válida tampoco se rescata
    assert model.calls == 2  # un solo reintento de validación


def test_si_el_principal_falla_responde_el_respaldo(
    session: Session, ref: ReferenceCatalog
) -> None:
    backup = _model(line_payload(ref.cafe_id, None, 1))
    agent = quote_agent(_model())

    chain = FallbackModel(failing_model(503), backup, fallback_on=(ModelHTTPError,))
    with agent.override(model=chain):
        quote = _cotizar(session, agent)

    assert quote.ai_outcome == AiOutcome.OK
    assert [line.unit_price for line in quote.lines] == [3500]


def test_si_fallan_el_principal_y_el_respaldo_queda_el_borrador_manual(
    session: Session, ref: ReferenceCatalog
) -> None:
    # pydantic-ai lanza un FallbackExceptionGroup, que no es un AgentRunError: con solo las
    # excepciones de research R4, justo la congestión daría un 500 en producción.
    agent = quote_agent(_model())

    chain = FallbackModel(failing_model(503), failing_model(429), fallback_on=(ModelHTTPError,))
    with agent.override(model=chain):
        quote = _cotizar(session, agent)

    _assert_manual_draft(quote, AiOutcome.PROVIDER_ERROR)


def test_el_respaldo_comparte_el_reloj_del_principal(
    session: Session, ref: ReferenceCatalog
) -> None:
    agent = quote_agent(_model())

    chain = FallbackModel(failing_model(503), slow_model(1), fallback_on=(ModelHTTPError,))
    with agent.override(model=chain):
        quote = _cotizar(session, agent, timeout=0.2)

    _assert_manual_draft(quote, AiOutcome.TIMEOUT)


def test_con_la_ia_desactivada_queda_el_borrador_manual_sin_duracion(
    session: Session, ref: ReferenceCatalog
) -> None:
    quote = _cotizar(session, None)

    _assert_manual_draft(quote, AiOutcome.DISABLED)
    assert quote.ai_duration_ms is None


@pytest.mark.parametrize("error", [TypeError("bug"), KeyError("bug"), RuntimeError("bug")])
def test_un_error_de_programacion_no_se_disfraza_de_falla_de_la_ia(
    session: Session, ref: ReferenceCatalog, error: Exception
) -> None:
    # RuntimeError importa: es la base de AgentRunError y lo que lanza el bloqueo de red.
    with pytest.raises(type(error)):
        _cotizar(session, quote_agent(raising_model(error)))

    assert quotes.list_quotes(session) == []


def test_un_error_al_armar_las_lineas_no_se_disfraza_de_falla_de_la_ia(
    session: Session, ref: ReferenceCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Un ValidationError de nuestro código no es una salida inválida de la IA.
    error = _validation_error()

    def broken(*_args: object) -> None:
        raise error

    monkeypatch.setattr(quotes, "build_lines", broken)

    with pytest.raises(ValidationError):
        _cotizar(session, quote_agent(_model()))


# Agregar una línea a mano (T036)


@pytest.fixture
def draft_id(session: Session, ref: ReferenceCatalog) -> int:
    quote = _cotizar(session, quote_agent(_model()))
    assert quote.id is not None
    return quote.id


def test_agregar_una_linea_toma_la_etiqueta_y_el_precio_del_catalogo(
    session: Session, ref: ReferenceCatalog, draft_id: int
) -> None:
    data = LineInput(item=f"{ref.torta_id}:{ref.mediana_id}", quantity=2)

    line = quotes.add_line(session, draft_id, data)

    assert line.id is not None
    assert (line.status, line.review_reason) == (LineStatus.LISTA, None)
    assert (line.product_id, line.variant_id) == (ref.torta_id, ref.mediana_id)
    assert line.label == "Torta de chocolate — Tamaño: Mediana"
    assert (line.unit_price, line.quantity, line.quantity_assumed) == (45000, 2, False)
    assert line.customer_text is None
    assert line.position == 1
    assert quotes.quote_total(quotes.get_quote(session, draft_id)) == 90000


def test_agregar_una_linea_usa_el_precio_vigente(
    session: Session, ref: ReferenceCatalog, draft_id: int
) -> None:
    cafe = session.get(Product, ref.cafe_id)
    assert cafe is not None
    cafe.price = 4000
    session.add(cafe)
    session.commit()

    line = quotes.add_line(session, draft_id, LineInput(item=str(ref.cafe_id), quantity=1))

    assert (line.variant_id, line.unit_price) == (None, 4000)


def test_una_linea_agregada_queda_al_final_aunque_se_haya_quitado_otra(
    session: Session, ref: ReferenceCatalog
) -> None:
    quote = _cotizar(
        session,
        quote_agent(_model(line_payload(ref.cafe_id, None, 1), line_payload(None, None, 1))),
    )
    assert quote.id is not None
    session.delete(quote.lines[0])  # queda solo la posición 2
    session.commit()
    session.refresh(quote)

    line = quotes.add_line(session, quote.id, LineInput(item=str(ref.cafe_id), quantity=1))

    assert line.position == 3


@pytest.mark.parametrize(
    "choice",
    ["inexistente", "sin_variante", "variante_de_otro", "producto_inactivo", "variante_inactiva"],
)
def test_no_se_agrega_un_item_que_no_es_cotizable(
    session: Session, ref: ReferenceCatalog, draft_id: int, choice: str
) -> None:
    cafe = session.get(Product, ref.cafe_id)
    grande = session.get(ProductVariant, ref.grande_id)
    assert cafe is not None
    assert grande is not None
    cafe.is_active = grande.is_active = False
    session.add_all([cafe, grande])
    session.commit()
    item = {
        "inexistente": "9999",
        "sin_variante": str(ref.torta_id),
        "variante_de_otro": f"{ref.cafe_id}:{ref.mediana_id}",
        "producto_inactivo": str(ref.cafe_id),
        "variante_inactiva": f"{ref.torta_id}:{ref.grande_id}",
    }[choice]

    with pytest.raises(quotes.ItemNotQuotableError):
        quotes.add_line(session, draft_id, LineInput(item=item, quantity=1))

    assert quotes.get_quote(session, draft_id).lines == []


def test_no_se_agrega_una_linea_a_una_cotizacion_inexistente(
    session: Session, ref: ReferenceCatalog
) -> None:
    with pytest.raises(quotes.QuoteNotFoundError):
        quotes.add_line(session, 999, LineInput(item=str(ref.cafe_id), quantity=1))


@pytest.mark.parametrize("quantity", ["0", "-1", "1000", "2.5", "muchas", ""])
def test_la_linea_manual_rechaza_una_cantidad_fuera_de_1_a_999(quantity: str) -> None:
    with pytest.raises(ValidationError):
        LineInput.model_validate({"item": "1", "quantity": quantity})


@pytest.mark.parametrize("item", ["", "cafe", "1:", ":2", "1:2:3", "-1", "1:dos", "1.5"])
def test_la_linea_manual_rechaza_un_item_con_otro_formato(item: str) -> None:
    with pytest.raises(ValidationError):
        LineInput.model_validate({"item": item, "quantity": "1"})


@pytest.mark.parametrize(("item", "quantity"), [("1", "1"), ("1:102", "999")])
def test_la_linea_manual_acepta_los_dos_formatos_de_item(item: str, quantity: str) -> None:
    data = LineInput.model_validate({"item": item, "quantity": quantity})

    assert (data.item, data.quantity) == (item, int(quantity))


# Historia 4: corregir el borrador (data-model.md, «Transiciones de una línea»)


@pytest.fixture
def draft(session: Session, ref: ReferenceCatalog) -> Quote:
    """Una lista (2 tortas medianas), dos por revisar y un café con cantidad supuesta."""
    model = _model(
        line_payload(ref.torta_id, ref.mediana_id, 2, "dos tortas medianas"),
        line_payload(None, None, 12, "una docena de empanadas"),
        line_payload(ref.torta_id, None, 1, "una torta de chocolate"),
        line_payload(ref.cafe_id, None, None, "un cafe"),
        delivery_date={"kind": "unknown"},
        delivery_time="a las 3",
        delivery_address="Calle 10 # 5-20",
    )
    quote = _cotizar(session, quote_agent(model))
    assert quotes.quote_total(quote) == 93500
    return quote


def _line_id(quote: Quote, position: int) -> int:
    line_id = quote.lines[position - 1].id
    assert line_id is not None
    return line_id


def _quote_id(quote: Quote) -> int:
    assert quote.id is not None
    return quote.id


def _reread(session: Session, quote: Quote) -> Quote:
    session.expire_all()
    return quotes.get_quote(session, _quote_id(quote))


def test_cambiar_solo_la_cantidad_conserva_el_precio_y_recalcula_el_total(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    data = LineInput(item=f"{ref.torta_id}:{ref.mediana_id}", quantity=3)

    line = quotes.update_line(session, _quote_id(draft), _line_id(draft, 1), data)

    assert (line.quantity, line.unit_price) == (3, 45000)
    assert quotes.quote_total(_reread(session, draft)) == 45000 * 3 + 3500


def test_cambiar_la_cantidad_no_toma_el_precio_nuevo_del_catalogo(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    # FR-015: la línea conserva el precio con que se cotizó.
    torta = session.get(Product, ref.torta_id)
    assert torta is not None
    torta.price = 50000  # la Mediana no tiene precio propio: hereda este
    session.add(torta)
    session.commit()
    data = LineInput(item=f"{ref.torta_id}:{ref.mediana_id}", quantity=3)

    line = quotes.update_line(session, _quote_id(draft), _line_id(draft, 1), data)

    assert line.unit_price == 45000


def test_cambiar_la_cantidad_de_algo_ya_desactivado_conserva_la_linea(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    cafe = session.get(Product, ref.cafe_id)
    assert cafe is not None
    cafe.is_active = False
    session.add(cafe)
    session.commit()

    line = quotes.update_line(
        session, _quote_id(draft), _line_id(draft, 4), LineInput(item=str(ref.cafe_id), quantity=2)
    )

    assert (line.status, line.quantity, line.unit_price) == (LineStatus.LISTA, 2, 3500)


def test_confirmar_la_cantidad_quita_la_marca_de_cantidad_supuesta(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    assert draft.lines[3].quantity_assumed is True

    line = quotes.update_line(
        session, _quote_id(draft), _line_id(draft, 4), LineInput(item=str(ref.cafe_id), quantity=1)
    )

    assert (line.quantity, line.quantity_assumed) == (1, False)


def test_cambiar_la_variante_copia_la_etiqueta_y_el_precio_vigentes(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    grande = session.get(ProductVariant, ref.grande_id)
    assert grande is not None
    grande.price = 65000  # cambió después de cotizar: al editar el ítem, vale el nuevo
    session.add(grande)
    session.commit()
    data = LineInput(item=f"{ref.torta_id}:{ref.grande_id}", quantity=2)

    line = quotes.update_line(session, _quote_id(draft), _line_id(draft, 1), data)

    assert (line.variant_id, line.unit_price) == (ref.grande_id, 65000)
    assert line.label == "Torta de chocolate — Tamaño: Grande"


@pytest.mark.parametrize("position", [2, 3], ids=["no_reconocido", "falta_variante"])
def test_elegir_un_item_resuelve_una_linea_por_revisar(
    session: Session, ref: ReferenceCatalog, draft: Quote, position: int
) -> None:
    text = draft.lines[position - 1].customer_text
    data = LineInput(item=f"{ref.torta_id}:{ref.mediana_id}", quantity=4)

    line = quotes.update_line(session, _quote_id(draft), _line_id(draft, position), data)

    assert (line.status, line.review_reason) == (LineStatus.LISTA, None)
    assert (line.product_id, line.variant_id) == (ref.torta_id, ref.mediana_id)
    assert (line.label, line.unit_price, line.quantity) == (
        "Torta de chocolate — Tamaño: Mediana",
        45000,
        4,
    )
    assert line.customer_text == text  # lo que pidió el cliente sigue a la vista
    stored = _reread(session, draft)
    assert quotes.pending_count(stored) == 1
    assert quotes.quote_total(stored) == 93500 + 45000 * 4


@pytest.mark.parametrize("position", [1, 2], ids=["lista", "por_revisar"])
def test_un_item_que_no_es_cotizable_no_cambia_la_linea(
    session: Session, ref: ReferenceCatalog, draft: Quote, position: int
) -> None:
    before = draft.lines[position - 1].model_dump()

    with pytest.raises(quotes.ItemNotQuotableError):
        quotes.update_line(
            session, _quote_id(draft), _line_id(draft, position), LineInput(item="9999", quantity=1)
        )

    assert _reread(session, draft).lines[position - 1].model_dump() == before


def test_no_se_edita_ni_se_quita_una_linea_de_otra_cotizacion(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    other = _cotizar(session, quote_agent(_model(line_payload(ref.cafe_id, None, 1))))
    foreign = _line_id(other, 1)
    data = LineInput(item=str(ref.cafe_id), quantity=5)

    with pytest.raises(quotes.QuoteLineNotFoundError):
        quotes.update_line(session, _quote_id(draft), foreign, data)
    with pytest.raises(quotes.QuoteLineNotFoundError):
        quotes.remove_line(session, _quote_id(draft), foreign)

    assert [line.quantity for line in _reread(session, other).lines] == [1]


def test_una_linea_o_una_cotizacion_inexistentes_no_se_encuentran(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    data = LineInput(item=str(ref.cafe_id), quantity=1)

    with pytest.raises(quotes.QuoteLineNotFoundError):
        quotes.update_line(session, _quote_id(draft), 999, data)
    with pytest.raises(quotes.QuoteLineNotFoundError):
        quotes.remove_line(session, _quote_id(draft), 999)
    with pytest.raises(quotes.QuoteNotFoundError):
        quotes.update_line(session, 999, _line_id(draft, 1), data)
    with pytest.raises(quotes.QuoteNotFoundError):
        quotes.update_delivery(session, 999, DeliveryInput())


def test_quitar_una_linea_la_borra_y_baja_el_total(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    quotes.remove_line(session, _quote_id(draft), _line_id(draft, 1))

    stored = _reread(session, draft)
    assert [line.position for line in stored.lines] == [2, 3, 4]
    assert quotes.quote_total(stored) == 3500


def test_quitar_las_lineas_por_revisar_deja_la_cotizacion_completa(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    # Los ids se leen antes de borrar: al quitar una línea, la lista se corre.
    ids = [_line_id(draft, 2), _line_id(draft, 3)]
    for line_id in ids:
        quotes.remove_line(session, _quote_id(draft), line_id)

    assert quotes.pending_count(_reread(session, draft)) == 0


def test_guardar_la_entrega_la_cambia_y_quita_las_tres_marcas(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    assert (
        draft.delivery_date_needs_review,
        draft.delivery_time_needs_review,
        draft.delivery_mode_needs_review,
    ) == (True, True, True)
    data = DeliveryInput(date="2026-11-28", time="15:30", mode="recoger", address=" Calle 1 ")

    quotes.update_delivery(session, _quote_id(draft), data)

    stored = _reread(session, draft)
    assert stored.delivery_date == datetime.date(2026, 11, 28)
    assert stored.delivery_time == datetime.time(15, 30)
    assert (stored.delivery_mode, stored.delivery_address) == ("recoger", "Calle 1")
    assert (
        stored.delivery_date_needs_review,
        stored.delivery_time_needs_review,
        stored.delivery_mode_needs_review,
    ) == (False, False, False)


def test_guardar_la_entrega_vacia_la_deja_sin_datos(
    session: Session, ref: ReferenceCatalog, draft: Quote
) -> None:
    quotes.update_delivery(session, _quote_id(draft), DeliveryInput())

    stored = _reread(session, draft)
    assert (stored.delivery_date, stored.delivery_time) == (None, None)
    assert (stored.delivery_mode, stored.delivery_address) == (None, None)
    assert not stored.delivery_mode_needs_review


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"date": "2026-02-30"}, id="fecha_inexistente"),
        pytest.param({"date": "28/11/2026"}, id="fecha_en_otro_formato"),
        pytest.param({"date": "mañana"}, id="fecha_en_palabras"),
        pytest.param({"time": "25:00"}, id="hora_25"),
        pytest.param({"time": "15:60"}, id="minuto_60"),
        pytest.param({"time": "3 pm"}, id="hora_en_palabras"),
        pytest.param({"mode": "envio"}, id="modalidad_desconocida"),
        pytest.param({"address": "x" * 201}, id="direccion_larga"),
    ],
)
def test_la_entrega_rechaza_datos_invalidos(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        DeliveryInput.model_validate(fields)


def test_la_entrega_acepta_la_direccion_de_200_caracteres() -> None:
    assert DeliveryInput(address="x" * 200).address == "x" * 200
