"""Páginas de cotización (contracts/quote-pages.md), con la sesión del dueño iniciada.

El extractor se sustituye con un agente sobre un `FunctionModel` (constitución II). El día y la
hora de Colombia se prueban congelando el reloj con time-machine (FR-021).
"""

import datetime
import re
from collections.abc import Iterator
from typing import Any

import pytest
import time_machine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.dependencies import get_quote_extractor
from app.models.catalog import Product
from app.models.quote import AiOutcome, LineStatus, Quote, QuoteLine, ReviewReason
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    failing_model,
    line_payload,
    log_in,
    quote_agent,
    seed_reference_catalog,
    slow_model,
)

QUOTE_URL = re.compile(r"/cotizaciones/(\d+)$")


@pytest.fixture
def ref(auth_app: FastAPI) -> ReferenceCatalog:
    with Session(auth_app.state.engine) as session:
        return seed_reference_catalog(session)


@pytest.fixture
def use_model(auth_app: FastAPI) -> Iterator[None]:
    yield
    auth_app.dependency_overrides.pop(get_quote_extractor, None)


def _install(app: FastAPI, model: ScriptedModel) -> ScriptedModel:
    agent = quote_agent(model)
    app.dependency_overrides[get_quote_extractor] = lambda: agent
    return model


def _two_products(ref: ReferenceCatalog, **delivery: object) -> ScriptedModel:
    return extraction_model(
        {
            **EMPTY_EXTRACTION,
            **delivery,
            "lines": [
                line_payload(ref.torta_id, ref.mediana_id, 2, "dos tortas medianas"),
                line_payload(ref.cafe_id, None, 1, "un cafe"),
            ],
        }
    )


def _post_quote(client: TestClient, message: str) -> int:
    response = client.post("/cotizaciones", data={"message": message}, follow_redirects=False)
    assert response.status_code == 303, response.text
    match = QUOTE_URL.search(response.headers["location"])
    assert match is not None
    return int(match.group(1))


def _stored_quote(app: FastAPI, quote_id: int) -> Quote:
    with Session(app.state.engine) as session:
        quote = session.get(Quote, quote_id)
        assert quote is not None
        return quote


# Nueva cotización


def test_el_formulario_pide_el_mensaje_y_se_desactiva_al_enviar(
    client: TestClient, ref: ReferenceCatalog
) -> None:
    html = client.get("/cotizaciones/nueva").text

    assert re.search(r'<textarea[^>]*name="message"[^>]*maxlength="2000"', html)
    assert "Cotizar" in html
    assert "Cotizando…" in html


def test_sin_nada_cotizable_el_formulario_invita_a_crear_productos(client: TestClient) -> None:
    html = client.get("/cotizaciones/nueva").text

    assert "Primero crea productos en el catálogo" in html
    assert 'href="/productos/nuevo"' in html
    assert "<textarea" not in html


def test_cotizar_redirige_al_detalle_con_precios_del_catalogo_y_total(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, _two_products(ref))

    quote_id = _post_quote(client, "dos tortas medianas y un cafe")
    html = client.get(f"/cotizaciones/{quote_id}").text

    assert f"Cotización n.º {quote_id}" in html
    assert "Borrador" in html
    assert "dos tortas medianas y un cafe" in html
    assert "Torta de chocolate — Tamaño: Mediana" in html
    assert "$ 45.000" in html  # precio unitario, del catálogo
    assert "$ 90.000" in html  # subtotal: 45.000 por 2
    assert "$ 3.500" in html
    assert "$ 93.500" in html  # total


def test_ninguna_pagina_tiene_un_campo_de_precio(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, _two_products(ref))
    quote_id = _post_quote(client, "dos tortas medianas y un cafe")

    for path in ("/cotizaciones/nueva", f"/cotizaciones/{quote_id}"):
        html = client.get(path).text
        assert not re.search(r'name="(unit_)?price"', html), path


# Día y hora de Colombia (time-machine)


def test_la_fecha_de_creacion_se_muestra_en_hora_de_colombia(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, _two_products(ref))
    # 03:30 UTC del sábado 21 es el viernes 20 a las 22:30 en Bogotá.
    with time_machine.travel(datetime.datetime(2026, 11, 21, 3, 30, tzinfo=datetime.UTC)):
        log_in(client)  # la sesión se firma a la hora simulada
        quote_id = _post_quote(client, "dos tortas medianas y un cafe")

    log_in(client)  # de vuelta a la hora real: la sesión simulada ya caducó
    html = client.get(f"/cotizaciones/{quote_id}").text

    assert "20/11/2026 22:30" in html


def test_las_fechas_relativas_se_resuelven_con_el_dia_de_colombia(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, _two_products(ref, delivery_date={"kind": "weekday", "weekday": 5}))
    # En UTC ya es sábado 21; en Bogotá aún es viernes 20, así que «el sábado» es mañana.
    with time_machine.travel(datetime.datetime(2026, 11, 21, 3, 30, tzinfo=datetime.UTC)):
        log_in(client)  # la sesión se firma a la hora simulada
        quote_id = _post_quote(client, "dos tortas medianas y un cafe para el sabado")

    quote = _stored_quote(auth_app, quote_id)
    assert quote.delivery_date == datetime.date(2026, 11, 21)
    assert quote.delivery_date_needs_review is False


# Validación: no se llama a la IA


def test_un_mensaje_vacio_vuelve_al_formulario_sin_llamar_a_la_ia(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    model = _install(auth_app, _two_products(ref))

    response = client.post("/cotizaciones", data={"message": "   "})

    assert response.status_code == 422
    assert "Pega el mensaje del cliente" in response.text
    assert model.calls == 0


def test_un_mensaje_demasiado_largo_conserva_lo_escrito_sin_llamar_a_la_ia(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    model = _install(auth_app, _two_products(ref))
    message = "mensaje-largo " * 150  # 2.100 caracteres

    response = client.post("/cotizaciones", data={"message": message})

    assert response.status_code == 422
    assert "El mensaje es demasiado largo (máximo 2.000 caracteres)" in response.text
    assert message.strip() in response.text
    assert model.calls == 0


def test_sin_nada_cotizable_cotizar_responde_409_sin_llamar_a_la_ia(
    client: TestClient, auth_app: FastAPI, use_model: None
) -> None:
    model = _install(auth_app, extraction_model(EMPTY_EXTRACTION))

    response = client.post("/cotizaciones", data={"message": "una torta"})

    assert response.status_code == 409
    assert "Primero crea productos en el catálogo" in response.text
    assert model.calls == 0


# Lista y navegación


def test_sin_cotizaciones_la_lista_invita_a_crear_una(client: TestClient) -> None:
    html = client.get("/cotizaciones").text

    assert "Aún no hay cotizaciones" in html
    assert 'href="/cotizaciones/nueva"' in html


def test_la_lista_va_de_la_mas_reciente_a_la_mas_antigua_con_su_total(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, _two_products(ref))
    with time_machine.travel(datetime.datetime(2026, 11, 20, 15, 0, tzinfo=datetime.UTC)):
        log_in(client)  # la sesión se firma a la hora simulada
        first = _post_quote(client, "dos tortas medianas y un cafe")
    with time_machine.travel(datetime.datetime(2026, 11, 20, 16, 0, tzinfo=datetime.UTC)):
        log_in(client)  # la sesión se firma a la hora simulada
        second = _post_quote(client, "dos tortas medianas y un cafe, otra vez")

    log_in(client)  # de vuelta a la hora real: la sesión simulada ya caducó
    html = client.get("/cotizaciones").text

    assert html.index(f'href="/cotizaciones/{second}"') < html.index(
        f'href="/cotizaciones/{first}"'
    )
    assert "Borrador" in html
    assert "$ 93.500" in html


def test_una_cotizacion_inexistente_responde_404(client: TestClient) -> None:
    response = client.get("/cotizaciones/999")

    # El mensaje de dominio distingue «la cotización no existe» de «la ruta no existe».
    assert response.status_code == 404
    assert response.json() == {"detail": "La cotización no existe"}


def test_la_navegacion_tiene_el_enlace_a_cotizaciones(client: TestClient) -> None:
    html = client.get("/productos").text

    assert 'href="/cotizaciones"' in html
    assert "Cotizaciones" in html


# Historia 2: «Por revisar». Casi todas guardan la cotización directamente, para que fallen por
# la plantilla y no por `build_lines`; la primera recorre el camino completo.

REASONS = {
    "una docena de empanadas": "No está en el catálogo",
    "una torta de chocolate": "Falta la presentación",
    "cero cafes": "Cantidad no válida",
}


def _line(**fields: Any) -> QuoteLine:
    # `quote_id` lo pone la relación al guardar, como en el servicio.
    return QuoteLine(**fields)


def _ready_line(ref: ReferenceCatalog) -> QuoteLine:
    return _line(
        position=1,
        customer_text="dos tortas medianas",
        status=LineStatus.LISTA,
        product_id=ref.torta_id,
        variant_id=ref.mediana_id,
        label="Torta de chocolate — Tamaño: Mediana",
        unit_price=45000,
        quantity=2,
    )


def _pending_lines(ref: ReferenceCatalog) -> list[QuoteLine]:
    cases = [
        ("una docena de empanadas", ReviewReason.NO_RECONOCIDO, None, 12),
        ("una torta de chocolate", ReviewReason.FALTA_VARIANTE, ref.torta_id, 1),
        ("cero cafes", ReviewReason.CANTIDAD_INVALIDA, ref.cafe_id, None),
    ]
    return [
        _line(
            position=position,
            customer_text=text,
            status=LineStatus.POR_REVISAR,
            review_reason=reason,
            product_id=product_id,
            quantity=quantity,
        )
        for position, (text, reason, product_id, quantity) in enumerate(cases, start=2)
    ]


def _save_quote(app: FastAPI, *lines: QuoteLine, **fields: Any) -> int:
    with Session(app.state.engine) as session:
        quote = Quote(
            customer_message="mensaje del cliente",
            created_at=datetime.datetime.now(datetime.UTC),
            ai_outcome=AiOutcome.OK,
            lines=list(lines),
            **fields,
        )
        session.add(quote)
        session.commit()
        assert quote.id is not None
        return quote.id


def _row_with(html: str, text: str) -> str:
    row: str
    (row,) = [row for row in re.findall(r"<tr\b.*?</tr>", html, re.DOTALL) if text in row]
    return row


def test_cotizar_algo_fuera_del_catalogo_muestra_la_linea_por_revisar(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    lines = [
        line_payload(ref.cafe_id, None, 2, "dos cafes"),
        line_payload(None, None, 12, "una docena de empanadas"),
        line_payload(ref.torta_id, None, 1, "una torta de chocolate"),
    ]
    _install(auth_app, extraction_model({**EMPTY_EXTRACTION, "lines": lines}))

    quote_id = _post_quote(client, "dos cafes, empanadas y una torta")
    html = client.get(f"/cotizaciones/{quote_id}").text

    assert "No está en el catálogo" in _row_with(html, "una docena de empanadas")
    assert "Falta la presentación" in _row_with(html, "una torta de chocolate")
    assert "Incompleta: 2 línea(s) por revisar" in html


@pytest.mark.parametrize(
    ("text", "reason"),
    REASONS.items(),
    ids=["no_reconocido", "falta_variante", "cantidad_invalida"],
)
def test_una_linea_por_revisar_muestra_su_motivo_y_el_texto_sin_precio(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, text: str, reason: str
) -> None:
    quote_id = _save_quote(auth_app, _ready_line(ref), *_pending_lines(ref))

    row = _row_with(client.get(f"/cotizaciones/{quote_id}").text, text)

    assert "Por revisar" in row
    assert reason in row
    assert all(other not in row for other in REASONS.values() if other != reason)
    assert "$" not in row  # ni precio unitario ni subtotal
    assert "None" not in row


@pytest.mark.parametrize("pending", [1, 2, 3])
def test_con_pendientes_el_encabezado_dice_cuantas_lineas_faltan(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, pending: int
) -> None:
    quote_id = _save_quote(auth_app, _ready_line(ref), *_pending_lines(ref)[:pending])

    html = client.get(f"/cotizaciones/{quote_id}").text

    header = html.partition("Mensaje del cliente")[0]
    assert f"Incompleta: {pending} línea(s) por revisar" in header


@pytest.mark.parametrize(
    ("with_ready", "total"),
    [pytest.param(True, "$ 90.000", id="mezcla"), pytest.param(False, "$ 0", id="solo_pendientes")],
)
def test_con_pendientes_el_total_avisa_que_no_las_incluye(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, with_ready: bool, total: str
) -> None:
    ready = [_ready_line(ref)] if with_ready else []
    quote_id = _save_quote(auth_app, *ready, *_pending_lines(ref))

    html = client.get(f"/cotizaciones/{quote_id}").text

    footer = html.partition("<tfoot>")[2].partition("</tfoot>")[0]
    assert total in footer
    assert "No incluye las líneas por revisar" in footer


def test_una_cotizacion_completa_no_muestra_avisos_de_revision(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _save_quote(auth_app, _ready_line(ref))

    html = client.get(f"/cotizaciones/{quote_id}").text

    for notice in ("Incompleta", "Por revisar", "por revisar", "Por confirmar"):
        assert notice not in html


def test_r09_un_mensaje_que_no_es_un_pedido_no_muestra_nada_por_revisar(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, extraction_model(EMPTY_EXTRACTION))

    quote_id = _post_quote(client, "buenas tardes, estan abiertos hoy?")
    html = client.get(f"/cotizaciones/{quote_id}").text

    assert "Esta cotización aún no tiene productos" in html
    for notice in ("Incompleta", "Por revisar", "por revisar"):
        assert notice not in html


@pytest.mark.parametrize(
    "field",
    [
        ("delivery_date_needs_review", "Fecha", "Hora"),
        ("delivery_time_needs_review", "Hora", "Modalidad"),
        ("delivery_mode_needs_review", "Modalidad", "Dirección"),
    ],
    ids=["fecha", "hora", "modalidad"],
)
def test_por_confirmar_aparece_solo_junto_al_dato_marcado(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, field: tuple[str, str, str]
) -> None:
    flag, label, next_label = field
    quote_id = _save_quote(auth_app, _ready_line(ref), **{flag: True})

    delivery = client.get(f"/cotizaciones/{quote_id}").text.partition("<h2>Entrega</h2>")[2]

    assert delivery.count("Por confirmar") == 1
    assert "Por confirmar" in delivery.partition(label)[2].partition(next_label)[0]


def test_la_lista_dice_cuantas_lineas_faltan_por_revisar(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    complete = _save_quote(auth_app, _ready_line(ref))
    incomplete = _save_quote(auth_app, _ready_line(ref), *_pending_lines(ref)[:2])

    html = client.get("/cotizaciones").text

    items = re.findall(r"<li>.*?</li>", html, re.DOTALL)
    (complete_item,) = [item for item in items if f'/cotizaciones/{complete}"' in item]
    (incomplete_item,) = [item for item in items if f'/cotizaciones/{incomplete}"' in item]
    assert "2 por revisar" in incomplete_item
    assert "por revisar" not in complete_item


# Historia 3: camino manual

NOTICES = {
    AiOutcome.TIMEOUT: "La IA no respondió a tiempo: agrega los productos a mano",
    AiOutcome.PROVIDER_ERROR: (
        "La IA no está disponible en este momento: agrega los productos a mano"
    ),
    AiOutcome.INVALID_OUTPUT: "La IA no entregó una respuesta válida: agrega los productos a mano",
    AiOutcome.DISABLED: "La IA está desactivada en este ambiente: agrega los productos a mano",
}


@pytest.fixture
def short_timeout(auth_app: FastAPI, use_model: None, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = auth_app.state.settings.model_copy(update={"ai_timeout_seconds": 0.2})
    monkeypatch.setattr(auth_app.state, "settings", settings)


@pytest.mark.parametrize("outcome", NOTICES, ids=lambda outcome: outcome.value)
def test_cada_falla_de_la_ia_lleva_al_borrador_con_su_aviso(
    client: TestClient,
    auth_app: FastAPI,
    ref: ReferenceCatalog,
    short_timeout: None,
    outcome: AiOutcome,
) -> None:
    if outcome is not AiOutcome.DISABLED:  # sin sustituir nada, la app de pruebas no tiene IA
        models = {
            AiOutcome.TIMEOUT: slow_model(1),
            AiOutcome.PROVIDER_ERROR: failing_model(503),
            AiOutcome.INVALID_OUTPUT: extraction_model({"lines": "no es una lista"}),
        }
        _install(auth_app, models[outcome])

    quote_id = _post_quote(client, "dos tortas medianas")  # 303
    html = client.get(f"/cotizaciones/{quote_id}").text

    assert NOTICES[outcome] in html
    assert "dos tortas medianas" in html


@pytest.mark.parametrize("outcome", NOTICES, ids=lambda outcome: outcome.value)
def test_el_detalle_muestra_solo_el_aviso_de_su_resultado_sin_detalles_tecnicos(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, outcome: AiOutcome
) -> None:
    quote_id = _failed_quote(auth_app, outcome)

    main = client.get(f"/cotizaciones/{quote_id}").text.partition("<main")[2]

    assert [notice for notice in NOTICES.values() if notice in main] == [NOTICES[outcome]]
    for detail in ("503", "Timeout", "timeout", "provider_error", "invalid_output", "Error"):
        assert detail not in main


def test_con_la_ia_bien_no_hay_aviso(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _save_quote(auth_app, _ready_line(ref))

    assert "agrega los productos a mano" not in client.get(f"/cotizaciones/{quote_id}").text


def _manual_draft(app: FastAPI) -> int:
    return _failed_quote(app, AiOutcome.TIMEOUT)


def _failed_quote(app: FastAPI, outcome: AiOutcome) -> int:
    quote_id = _save_quote(app)
    with Session(app.state.engine) as session:
        quote = session.get(Quote, quote_id)
        assert quote is not None
        quote.ai_outcome = outcome
        session.add(quote)
        session.commit()
    return quote_id


def test_el_formulario_de_agregar_ofrece_solo_lo_cotizable(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _manual_draft(auth_app)

    html = client.get(f"/cotizaciones/{quote_id}").text

    action = f'action="/cotizaciones/{quote_id}/lineas"'
    assert action in html
    form = html.partition(action)[2].partition("</form>")[0]
    assert "Agregar producto" in html
    assert re.search(r'<select[^>]*name="item"', form)
    assert re.search(r'<input[^>]*name="quantity"', form)
    values = set(re.findall(r'<option[^>]*value="([^"]+)"', form))
    assert values == {
        f"{ref.torta_id}:{ref.mediana_id}",
        f"{ref.torta_id}:{ref.grande_id}",
        str(ref.cafe_id),
    }
    assert "Torta de chocolate — Tamaño: Mediana" in form
    assert not re.search(r'name="(unit_)?price"', form)


def test_agregar_una_linea_redirige_y_muestra_su_precio_y_el_total(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _manual_draft(auth_app)
    data = {"item": f"{ref.torta_id}:{ref.mediana_id}", "quantity": "2"}

    response = client.post(f"/cotizaciones/{quote_id}/lineas", data=data, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/cotizaciones/{quote_id}")
    html = client.get(f"/cotizaciones/{quote_id}").text
    assert "$ 45.000" in html
    assert "$ 90.000" in html.partition("<tfoot>")[2].partition("</tfoot>")[0]


def test_un_precio_enviado_a_mano_se_ignora(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _manual_draft(auth_app)
    data = {"item": str(ref.cafe_id), "quantity": "1", "price": "1", "unit_price": "1"}

    response = client.post(f"/cotizaciones/{quote_id}/lineas", data=data, follow_redirects=False)

    assert response.status_code == 303
    assert [line.unit_price for line in _stored_lines(auth_app, quote_id)] == [3500]


def _stored_lines(app: FastAPI, quote_id: int) -> list[QuoteLine]:
    with Session(app.state.engine) as session:
        quote = session.get(Quote, quote_id)
        assert quote is not None
        return list(quote.lines)


@pytest.mark.parametrize("quantity", ["0", "-1", "1000", "2.5", "abc", ""])
def test_una_cantidad_no_valida_vuelve_al_detalle_con_422_y_lo_escrito(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, quantity: str
) -> None:
    quote_id = _manual_draft(auth_app)
    item = f"{ref.torta_id}:{ref.grande_id}"

    response = client.post(
        f"/cotizaciones/{quote_id}/lineas", data={"item": item, "quantity": quantity}
    )

    assert response.status_code == 422
    assert "La cantidad debe ser un número entero entre 1 y 999" in response.text
    assert re.search(rf'<option[^>]*value="{item}"[^>]*\bselected\b', response.text)
    if quantity:
        assert f'value="{quantity}"' in response.text
    assert _stored_lines(auth_app, quote_id) == []


@pytest.mark.parametrize("choice", ["inactivo", "inexistente", "mal_formado", "vacio"])
def test_un_item_que_no_es_cotizable_vuelve_al_detalle_con_422(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, choice: str
) -> None:
    with Session(auth_app.state.engine) as session:
        cafe = session.get(Product, ref.cafe_id)
        assert cafe is not None
        cafe.is_active = False
        session.add(cafe)
        session.commit()
    quote_id = _manual_draft(auth_app)
    item = {
        "inactivo": str(ref.cafe_id),
        "inexistente": "9999",
        "mal_formado": "cafe",
        "vacio": "",
    }[choice]

    response = client.post(f"/cotizaciones/{quote_id}/lineas", data={"item": item, "quantity": "1"})

    assert response.status_code == 422
    assert "Ese producto ya no está disponible en el catálogo" in response.text
    assert _stored_lines(auth_app, quote_id) == []


def test_agregar_a_una_cotizacion_inexistente_responde_404(
    client: TestClient, ref: ReferenceCatalog
) -> None:
    response = client.post(
        "/cotizaciones/999/lineas", data={"item": str(ref.cafe_id), "quantity": "1"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "La cotización no existe"}


# Historia 4: corregir el borrador


def _draft(app: FastAPI, ref: ReferenceCatalog, **fields: Any) -> int:
    """Una lista (2 tortas medianas) y las tres por revisar de `_pending_lines`."""
    return _save_quote(app, _ready_line(ref), *_pending_lines(ref), **fields)


def _line_ids(app: FastAPI, quote_id: int) -> list[int]:
    return [line.id for line in _stored_lines(app, quote_id) if line.id is not None]


def _form_for(html: str, action: str) -> str:
    marker = f'action="{action}"'
    assert marker in html, action
    return html.partition(marker)[2].partition("</form>")[0]


def test_cada_linea_tiene_su_formulario_de_edicion_y_de_eliminacion(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _draft(auth_app, ref)
    ready, *pending = _line_ids(auth_app, quote_id)

    html = client.get(f"/cotizaciones/{quote_id}").text

    edit = _form_for(html, f"/cotizaciones/{quote_id}/lineas/{ready}")
    assert re.search(rf'<option[^>]*value="{ref.torta_id}:{ref.mediana_id}"[^>]*\bselected\b', edit)
    assert re.search(r'<input[^>]*name="quantity"[^>]*value="2"', edit)
    _form_for(html, f"/cotizaciones/{quote_id}/lineas/{ready}/eliminar")
    for line_id in pending:
        form = _form_for(html, f"/cotizaciones/{quote_id}/lineas/{line_id}")
        assert re.search(r'<select[^>]*name="item"', form)
        _form_for(html, f"/cotizaciones/{quote_id}/lineas/{line_id}/eliminar")
    assert not re.search(r'name="(unit_)?price"', html)


def test_una_linea_sin_presentacion_muestra_el_producto_que_identifico(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    # Escenario 2.2: el producto ya está identificado; solo falta elegir la presentación.
    quote_id = _draft(auth_app, ref)

    row = _row_with(client.get(f"/cotizaciones/{quote_id}").text, "una torta de chocolate")

    assert "Falta la presentación" in row
    assert "Torta de chocolate" in row.replace("una torta de chocolate", "")


def test_cambiar_la_cantidad_redirige_y_recalcula_subtotal_y_total(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _draft(auth_app, ref)
    ready = _line_ids(auth_app, quote_id)[0]
    data = {"item": f"{ref.torta_id}:{ref.mediana_id}", "quantity": "3"}

    response = client.post(
        f"/cotizaciones/{quote_id}/lineas/{ready}", data=data, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/cotizaciones/{quote_id}")
    html = client.get(f"/cotizaciones/{quote_id}").text
    assert "$ 135.000" in html.partition("<tfoot>")[2].partition("</tfoot>")[0]


def test_resolver_las_lineas_por_revisar_quita_los_avisos(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _draft(auth_app, ref)
    for line_id in _line_ids(auth_app, quote_id)[1:]:
        data = {"item": str(ref.cafe_id), "quantity": "1"}
        response = client.post(
            f"/cotizaciones/{quote_id}/lineas/{line_id}", data=data, follow_redirects=False
        )
        assert response.status_code == 303

    html = client.get(f"/cotizaciones/{quote_id}").text

    for notice in ("Incompleta", "Por revisar", "No incluye las líneas por revisar"):
        assert notice not in html
    assert (
        "$ 100.500" in html.partition("<tfoot>")[2].partition("</tfoot>")[0]
    )  # 90.000 más 3 cafés de 3.500


def test_eliminar_una_linea_redirige_y_baja_el_total(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _save_quote(auth_app, _ready_line(ref))
    ready = _line_ids(auth_app, quote_id)[0]

    response = client.post(
        f"/cotizaciones/{quote_id}/lineas/{ready}/eliminar", follow_redirects=False
    )

    assert response.status_code == 303
    assert _stored_lines(auth_app, quote_id) == []
    assert "Esta cotización aún no tiene productos" in client.get(f"/cotizaciones/{quote_id}").text


def test_un_precio_enviado_al_editar_se_ignora(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _draft(auth_app, ref)
    ready = _line_ids(auth_app, quote_id)[0]
    data = {
        "item": f"{ref.torta_id}:{ref.grande_id}",
        "quantity": "1",
        "unit_price": "1",
        "price": "1",
    }

    client.post(f"/cotizaciones/{quote_id}/lineas/{ready}", data=data, follow_redirects=False)

    assert _stored_lines(auth_app, quote_id)[0].unit_price == 60000


@pytest.mark.parametrize("quantity", ["0", "-1", "abc"])
def test_una_cantidad_no_valida_al_editar_responde_422_sin_cambiar_la_linea(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, quantity: str
) -> None:
    quote_id = _draft(auth_app, ref)
    ready = _line_ids(auth_app, quote_id)[0]
    data = {"item": f"{ref.torta_id}:{ref.mediana_id}", "quantity": quantity}

    response = client.post(f"/cotizaciones/{quote_id}/lineas/{ready}", data=data)

    assert response.status_code == 422
    form = _form_for(response.text, f"/cotizaciones/{quote_id}/lineas/{ready}")
    assert "La cantidad debe ser un número entero entre 1 y 999" in form
    assert f'value="{quantity}"' in form
    assert _stored_lines(auth_app, quote_id)[0].quantity == 2


def test_un_item_no_cotizable_al_editar_responde_422(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    quote_id = _draft(auth_app, ref)
    pending = _line_ids(auth_app, quote_id)[1]

    response = client.post(
        f"/cotizaciones/{quote_id}/lineas/{pending}", data={"item": "9999", "quantity": "1"}
    )

    assert response.status_code == 422
    form = _form_for(response.text, f"/cotizaciones/{quote_id}/lineas/{pending}")
    assert "Ese producto ya no está disponible en el catálogo" in form


@pytest.mark.parametrize("action", ["", "/eliminar"], ids=["editar", "eliminar"])
def test_una_linea_de_otra_cotizacion_responde_404(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, action: str
) -> None:
    quote_id = _draft(auth_app, ref)
    other = _save_quote(auth_app, _ready_line(ref))
    foreign = _line_ids(auth_app, other)[0]
    data = {"item": str(ref.cafe_id), "quantity": "5"}

    response = client.post(f"/cotizaciones/{quote_id}/lineas/{foreign}{action}", data=data)

    assert response.status_code == 404
    assert [line.quantity for line in _stored_lines(auth_app, other)] == [2]


def test_guardar_la_entrega_la_muestra_y_quita_por_confirmar(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog
) -> None:
    flags = {
        "delivery_date_needs_review": True,
        "delivery_time_needs_review": True,
        "delivery_mode_needs_review": True,
    }
    quote_id = _save_quote(auth_app, _ready_line(ref), **flags)
    data = {"date": "2026-11-28", "time": "15:30", "mode": "domicilio", "address": "Calle 1"}

    response = client.post(f"/cotizaciones/{quote_id}/entrega", data=data, follow_redirects=False)

    assert response.status_code == 303
    delivery = client.get(f"/cotizaciones/{quote_id}").text.partition("<h2>Entrega</h2>")[2]
    for shown in ("28/11/2026", "15:30", "Domicilio", "Calle 1"):
        assert shown in delivery
    assert "Por confirmar" not in delivery


ENTREGA_VALIDA = {"date": "2026-11-28", "time": "15:30", "mode": "recoger", "address": "Calle 1"}


@pytest.mark.parametrize(
    "case",
    [
        ("date", "2026-02-30", "Escribe una fecha válida"),
        ("time", "25:00", "Escribe una hora válida (HH:MM)"),
        ("address", "x" * 201, "La dirección admite máximo 200 caracteres"),
    ],
    ids=["fecha", "hora", "direccion"],
)
def test_una_entrega_invalida_responde_422_con_lo_escrito_sin_cambiar_nada(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, case: tuple[str, str, str]
) -> None:
    field, value, message = case
    quote_id = _save_quote(auth_app, _ready_line(ref), delivery_address="Calle 10")
    data = {**ENTREGA_VALIDA, field: value}

    response = client.post(f"/cotizaciones/{quote_id}/entrega", data=data)

    assert response.status_code == 422
    form = _form_for(response.text, f"/cotizaciones/{quote_id}/entrega")
    assert message in form
    # Lo escrito no se pierde, ni lo inválido ni lo demás.
    for name, typed in data.items():
        if name == "mode":
            assert re.search(r'<option[^>]*value="recoger"[^>]*\bselected\b', form)
        else:
            assert f'value="{typed}"' in form, name
    with Session(auth_app.state.engine) as session:
        stored = session.get(Quote, quote_id)
        assert stored is not None
        assert (stored.delivery_date, stored.delivery_address) == (None, "Calle 10")


def test_la_entrega_de_una_cotizacion_inexistente_responde_404(client: TestClient) -> None:
    response = client.post("/cotizaciones/999/entrega", data={"date": ""})

    assert response.status_code == 404
