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

from app.models.quote import AiOutcome, LineStatus, Quote, QuoteLine, ReviewReason
from app.routers.quotes import get_quote_extractor
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    line_payload,
    log_in,
    quote_agent,
    seed_reference_catalog,
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
