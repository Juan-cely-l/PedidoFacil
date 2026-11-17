"""Reglas puras del catálogo: precio en pesos y normalización de nombres."""

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from app.models.catalog import (
    PRICE_GROUPING_MESSAGE,
    PRICE_INVALID_MESSAGE,
    PRICE_TOO_HIGH_MESSAGE,
    Product,
    ProductInput,
    ProductVariant,
    VariantInput,
    VariantKind,
    clean_text,
    normalize_key,
    parse_price,
)
from app.services.catalog import effective_price

# Precio en pesos (T004)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("45.000", 45000),
        ("45 000", 45000),
        ("45000", 45000),
        (" 45000 ", 45000),
        ("1.250.000", 1250000),
        ("45\u00a0000", 45000),  # espacio no separable
        ("45\u202f000", 45000),  # espacio fino no separable
        ("1", 1),
        ("100.000.000", 100_000_000),
    ],
)
def test_precio_valido_se_convierte_a_entero(raw: str, expected: int) -> None:
    assert parse_price(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["45.00", "4.5", "45000.000", "45.0000", "4.50.000", "45 00", ".45", "45."],
)
def test_precio_con_puntos_mal_agrupados_explica_que_el_punto_separa_miles(raw: str) -> None:
    with pytest.raises(PydanticCustomError) as error:
        parse_price(raw)
    assert error.value.message() == PRICE_GROUPING_MESSAGE
    assert PRICE_GROUPING_MESSAGE == (
        "Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos"
    )


@pytest.mark.parametrize(
    "raw",
    ["45,5", "45,000", "", "   ", "0", "0.000", "-5", "abc", "5e3", "5_000"],
)
def test_precio_invalido_se_rechaza(raw: str) -> None:
    with pytest.raises(PydanticCustomError) as error:
        parse_price(raw)
    assert error.value.message() == PRICE_INVALID_MESSAGE
    assert PRICE_INVALID_MESSAGE == "El precio debe ser un número entero mayor que cero"


@pytest.mark.parametrize("raw", ["100000001", "150.000.000"])
def test_precio_por_encima_del_maximo_sugiere_error_de_digitacion(raw: str) -> None:
    with pytest.raises(PydanticCustomError) as error:
        parse_price(raw)
    assert error.value.message() == PRICE_TOO_HIGH_MESSAGE
    assert PRICE_TOO_HIGH_MESSAGE == (
        "El precio supera 100.000.000; revisa si hay un error de digitación"
    )


# Normalización de nombres (T005)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  Brownie ", "brownie"),
        ("Torta  Negra", "torta negra"),
        ("CAFÉ", "cafe"),
        ("Pingüino", "pinguino"),
        ("Piña", "piña"),
        ("AÑO", "año"),
    ],
)
def test_normalize_key_ignora_mayusculas_tildes_y_espacios(text: str, expected: str) -> None:
    assert normalize_key(text) == expected


def test_normalize_key_trata_igual_te_con_y_sin_tilde() -> None:
    assert normalize_key("Té") == normalize_key("te")


def test_normalize_key_conserva_la_enie() -> None:
    assert normalize_key("Piña") != normalize_key("Pina")
    assert normalize_key("Año") != normalize_key("Ano")


def test_normalize_key_conserva_la_enie_escrita_descompuesta() -> None:
    # «n» + virgulilla combinante (U+0303), como llega a veces desde otros sistemas.
    assert normalize_key("Pin\u0303a") == "piña"


def test_clean_text_recorta_y_colapsa_espacios_sin_cambiar_mayusculas_ni_tildes() -> None:
    assert clean_text("  Torta   Negra ") == "Torta Negra"
    assert clean_text(" Café\u00a0 Molido ") == "Café Molido"


# Datos del formulario de producto (T009)


def _errors_by_field(error: ValidationError) -> dict[str, str]:
    return {str(item["loc"][0]): item["msg"] for item in error.errors()}


def test_product_input_limpia_el_texto_y_convierte_el_precio() -> None:
    data = ProductInput.model_validate(
        {"name": "  Torta   Negra ", "description": "  Húmeda  ", "price": "45.000"}
    )

    assert data.name == "Torta Negra"
    assert data.description == "Húmeda"
    assert data.price == 45000
    assert data.tracks_inventory is False


def test_product_input_descripcion_es_opcional() -> None:
    data = ProductInput.model_validate({"name": "Brownie", "price": "5000"})

    assert data.description == ""


def test_product_input_casilla_marcada_controla_inventario() -> None:
    data = ProductInput.model_validate(
        {"name": "Brownie", "price": "5000", "tracks_inventory": "on"}
    )

    assert data.tracks_inventory is True


def test_product_input_acepta_nombre_de_100_y_descripcion_de_200_caracteres() -> None:
    data = ProductInput.model_validate({"name": "n" * 100, "description": "d" * 200, "price": "1"})

    assert len(data.name) == 100
    assert len(data.description) == 200


@pytest.mark.parametrize("name", ["", "   "])
def test_product_input_nombre_vacio_es_obligatorio(name: str) -> None:
    with pytest.raises(ValidationError) as error:
        ProductInput.model_validate({"name": name, "price": "5000"})

    assert _errors_by_field(error.value) == {"name": "El nombre es obligatorio"}


def test_product_input_reporta_un_error_por_campo() -> None:
    with pytest.raises(ValidationError) as error:
        ProductInput.model_validate({"name": "n" * 101, "description": "d" * 201, "price": "45,5"})

    assert _errors_by_field(error.value) == {
        "name": "El nombre admite máximo 100 caracteres",
        "description": "La descripción admite máximo 200 caracteres",
        "price": PRICE_INVALID_MESSAGE,
    }


def test_product_input_precio_mal_agrupado_usa_el_mensaje_de_miles() -> None:
    with pytest.raises(ValidationError) as error:
        ProductInput.model_validate({"name": "Brownie", "price": "45.00"})

    assert _errors_by_field(error.value) == {"price": PRICE_GROUPING_MESSAGE}


# Datos del formulario de variante y precio efectivo (T018)


@pytest.mark.parametrize("kind", ["sabor", "peso", "color", "marca", "tamano"])
def test_variant_input_acepta_los_cinco_tipos(kind: str) -> None:
    data = VariantInput.model_validate({"kind": kind, "value": "Chocolate", "price": ""})

    assert data.kind == VariantKind(kind)


@pytest.mark.parametrize("kind", ["talla", "", "Sabor"])
def test_variant_input_tipo_desconocido_se_rechaza(kind: str) -> None:
    with pytest.raises(ValidationError) as error:
        VariantInput.model_validate({"kind": kind, "value": "Chocolate", "price": ""})

    assert _errors_by_field(error.value) == {"kind": "Elige un tipo de variante válido"}


def test_variant_input_limpia_el_valor() -> None:
    data = VariantInput.model_validate({"kind": "peso", "value": "  500   g ", "price": ""})

    assert data.value == "500 g"


@pytest.mark.parametrize("value", ["", "   "])
def test_variant_input_valor_vacio_es_obligatorio(value: str) -> None:
    with pytest.raises(ValidationError) as error:
        VariantInput.model_validate({"kind": "peso", "value": value, "price": ""})

    assert _errors_by_field(error.value) == {"value": "El valor de la variante es obligatorio"}


def test_variant_input_acepta_valor_de_50_y_rechaza_51_caracteres() -> None:
    data = VariantInput.model_validate({"kind": "sabor", "value": "v" * 50, "price": ""})
    assert len(data.value) == 50

    with pytest.raises(ValidationError) as error:
        VariantInput.model_validate({"kind": "sabor", "value": "v" * 51, "price": ""})

    assert _errors_by_field(error.value) == {"value": "El valor admite máximo 50 caracteres"}


@pytest.mark.parametrize("price", ["", "   "])
def test_variant_input_sin_precio_usa_el_del_producto(price: str) -> None:
    data = VariantInput.model_validate({"kind": "peso", "value": "250 g", "price": price})

    assert data.price is None


def test_variant_input_convierte_el_precio_propio() -> None:
    data = VariantInput.model_validate({"kind": "peso", "value": "500 g", "price": "32.000"})

    assert data.price == 32000


@pytest.mark.parametrize(
    ("price", "message"),
    [("45,5", PRICE_INVALID_MESSAGE), ("45.00", PRICE_GROUPING_MESSAGE)],
)
def test_variant_input_precio_invalido_usa_los_mensajes_del_producto(
    price: str, message: str
) -> None:
    with pytest.raises(ValidationError) as error:
        VariantInput.model_validate({"kind": "peso", "value": "500 g", "price": price})

    assert _errors_by_field(error.value) == {"price": message}


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        (VariantKind.SABOR, "Sabor"),
        (VariantKind.PESO, "Peso"),
        (VariantKind.COLOR, "Color"),
        (VariantKind.MARCA, "Marca"),
        (VariantKind.TAMANO, "Tamaño"),
    ],
)
def test_variant_kind_tiene_etiqueta_en_espanol(kind: VariantKind, label: str) -> None:
    assert kind.label == label


def _coffee(price: int = 18000) -> Product:
    return Product(id=1, name="Café", name_key="cafe", price=price)


def _variant(price: int | None) -> ProductVariant:
    return ProductVariant(product_id=1, kind="peso", value="500 g", value_key="500 g", price=price)


def test_precio_efectivo_sin_precio_propio_es_el_del_producto() -> None:
    assert effective_price(_coffee(18000), _variant(None)) == 18000


def test_precio_efectivo_con_precio_propio_es_el_de_la_variante() -> None:
    assert effective_price(_coffee(18000), _variant(32000)) == 32000
