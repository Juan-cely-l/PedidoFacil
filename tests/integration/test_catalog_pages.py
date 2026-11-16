"""Páginas del catálogo (contracts/catalog-pages.md)."""

import re

import httpx2  # el cliente HTTP que usa TestClient (llega con fastapi[standard])
import pytest
from fastapi.testclient import TestClient

from app.models.catalog import (
    PRICE_GROUPING_MESSAGE,
    PRICE_INVALID_MESSAGE,
    PRICE_TOO_HIGH_MESSAGE,
)

DUPLICATE_PRODUCT_MESSAGE = "Ya existe un producto activo con ese nombre"


def create_product(client: TestClient, **fields: str) -> httpx2.Response:
    data = {
        "name": "Brownie",
        "description": "Brownie de chocolate",
        "price": "45.000",
        "tracks_inventory": "on",
    } | fields
    return client.post("/productos", data=data, follow_redirects=False)


def created_detail(client: TestClient, response: httpx2.Response) -> str:
    assert response.status_code == 303
    location = response.headers["location"]
    assert re.fullmatch(r"/productos/\d+", location)
    detail = client.get(location)
    assert detail.status_code == 200
    return detail.text


def test_listado_vacio_invita_a_crear_un_producto(client: TestClient) -> None:
    response = client.get("/productos")

    assert response.status_code == 200
    assert "Aún no hay productos" in response.text
    assert 'href="/productos/nuevo"' in response.text


def test_formulario_nuevo_tiene_todos_los_campos(client: TestClient) -> None:
    response = client.get("/productos/nuevo")

    assert response.status_code == 200
    for field in ("name", "description", "price", "tracks_inventory"):
        assert f'name="{field}"' in response.text


def test_crear_producto_redirige_al_detalle_con_sus_datos(client: TestClient) -> None:
    html = created_detail(client, create_product(client))

    assert "Brownie" in html
    assert "Brownie de chocolate" in html
    assert "$ 45.000" in html
    assert "Controla inventario: sí" in html


def test_producto_sin_casilla_no_controla_inventario(client: TestClient) -> None:
    data = {"name": "Brownie", "description": "", "price": "5000"}
    response = client.post("/productos", data=data, follow_redirects=False)

    assert "Controla inventario: no" in created_detail(client, response)


@pytest.mark.parametrize("price", ["45.000", "45 000", "45000"])
def test_precio_con_o_sin_separador_de_miles_se_guarda_igual(
    client: TestClient, price: str
) -> None:
    html = created_detail(client, create_product(client, price=price))

    assert "$ 45.000" in html


@pytest.mark.parametrize(
    ("price", "message"),
    [
        ("45,5", PRICE_INVALID_MESSAGE),
        ("45.00", PRICE_GROUPING_MESSAGE),
        ("150.000.000", PRICE_TOO_HIGH_MESSAGE),
    ],
)
def test_precio_invalido_vuelve_al_formulario_sin_perder_lo_escrito(
    client: TestClient, price: str, message: str
) -> None:
    response = create_product(client, price=price)

    assert response.status_code == 422
    assert message in response.text
    assert 'value="Brownie"' in response.text
    assert f'value="{price}"' in response.text
    assert 'aria-invalid="true"' in response.text


def test_nombre_vacio_es_obligatorio(client: TestClient) -> None:
    response = create_product(client, name="")

    assert response.status_code == 422
    assert "El nombre es obligatorio" in response.text


def test_nombre_activo_repetido_responde_conflicto(client: TestClient) -> None:
    create_product(client, name="Brownie")

    response = create_product(client, name="BROWNIE ")

    assert response.status_code == 409
    assert DUPLICATE_PRODUCT_MESSAGE in response.text
    assert 'value="BROWNIE "' in response.text


def test_producto_inexistente_responde_404(client: TestClient) -> None:
    assert client.get("/productos/999").status_code == 404


def test_listado_ordena_por_nombre_y_muestra_precios(client: TestClient) -> None:
    for name in ["Torta", "arequipe", "Brownie"]:
        create_product(client, name=name)

    html = client.get("/productos").text

    assert html.index("arequipe") < html.index("Brownie") < html.index("Torta")
    assert "$ 45.000" in html


def test_nombre_con_html_se_muestra_escapado(client: TestClient) -> None:
    html = created_detail(client, create_product(client, name="<script>alert(1)</script>"))

    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
