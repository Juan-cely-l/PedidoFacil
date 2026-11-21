"""Páginas de cotización (contracts/quote-pages.md), con la sesión del dueño iniciada.

El extractor se sustituye con un agente sobre un `FunctionModel` (constitución II). El día y la
hora de Colombia se prueban congelando el reloj con time-machine (FR-021).
"""

import datetime
import re
from collections.abc import Iterator

import pytest
import time_machine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.quote import Quote
from app.routers.quotes import get_quote_extractor
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    line_payload,
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
        quote_id = _post_quote(client, "dos tortas medianas y un cafe")

    html = client.get(f"/cotizaciones/{quote_id}").text

    assert "20/11/2026 22:30" in html


def test_las_fechas_relativas_se_resuelven_con_el_dia_de_colombia(
    client: TestClient, auth_app: FastAPI, ref: ReferenceCatalog, use_model: None
) -> None:
    _install(auth_app, _two_products(ref, delivery_date={"kind": "weekday", "weekday": 5}))
    # En UTC ya es sábado 21; en Bogotá aún es viernes 20, así que «el sábado» es mañana.
    with time_machine.travel(datetime.datetime(2026, 11, 21, 3, 30, tzinfo=datetime.UTC)):
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
        first = _post_quote(client, "dos tortas medianas y un cafe")
    with time_machine.travel(datetime.datetime(2026, 11, 20, 16, 0, tzinfo=datetime.UTC)):
        second = _post_quote(client, "dos tortas medianas y un cafe, otra vez")

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
