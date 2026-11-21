"""Las migraciones de Alembic crean exactamente el esquema de los modelos.

Se ejecutan sobre SQLite en memoria (constitución, principio II): la conexión se le pasa a
Alembic en `config.attributes`, y `migrations/env.py` la usa en lugar de leer la configuración.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registra las tablas en SQLModel.metadata)
from app.db import build_engine

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture
def alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


@pytest.fixture
def connection(alembic_config: Config) -> Iterator[Connection]:
    """Conexión en memoria con todas las migraciones aplicadas."""
    engine = build_engine("sqlite://")
    with engine.begin() as conn:
        alembic_config.attributes["connection"] = conn
        command.upgrade(alembic_config, "head")
        yield conn
    engine.dispose()


def test_migraciones_crean_la_tabla_de_productos(connection: Connection) -> None:
    assert "product" in inspect(connection).get_table_names()


def test_migraciones_coinciden_con_los_modelos(connection: Connection) -> None:
    differences = compare_metadata(MigrationContext.configure(connection), SQLModel.metadata)

    assert differences == []


def test_la_base_rechaza_un_producto_con_precio_cero(connection: Connection) -> None:
    # En SQLite, una sentencia fallida no invalida la transacción en curso.
    with pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO product (name, name_key, description, price, tracks_inventory, "
                "is_active) VALUES ('Brownie', 'brownie', '', 0, 0, 1)"
            )
        )


def test_la_base_rechaza_dos_productos_activos_con_la_misma_clave(
    connection: Connection,
) -> None:
    insert = text(
        "INSERT INTO product (name, name_key, description, price, tracks_inventory, is_active) "
        "VALUES (:name, 'brownie', '', 5000, 0, :active)"
    )
    connection.execute(insert, {"name": "Brownie", "active": False})
    connection.execute(insert, {"name": "Brownie", "active": True})

    with pytest.raises(IntegrityError):
        connection.execute(insert, {"name": "brownie", "active": True})


def test_migraciones_crean_la_tabla_de_variantes(connection: Connection) -> None:
    assert "product_variant" in inspect(connection).get_table_names()


def _insert_coffee(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO product (id, name, name_key, description, price, tracks_inventory, "
            "is_active) VALUES (1, 'Café', 'cafe', '', 18000, 0, 1)"
        )
    )


INSERT_VARIANT = text(
    "INSERT INTO product_variant (product_id, kind, value, value_key, price, is_active) "
    "VALUES (1, :kind, '500 g', '500 g', :price, :active)"
)


def test_la_base_rechaza_un_tipo_de_variante_desconocido(connection: Connection) -> None:
    _insert_coffee(connection)

    # En SQLite, una sentencia fallida no invalida la transacción en curso (como en T010).
    with pytest.raises(IntegrityError):
        connection.execute(INSERT_VARIANT, {"kind": "talla", "price": None, "active": True})


def test_la_base_rechaza_una_variante_con_precio_cero(connection: Connection) -> None:
    _insert_coffee(connection)

    with pytest.raises(IntegrityError):
        connection.execute(INSERT_VARIANT, {"kind": "peso", "price": 0, "active": True})


def test_la_base_rechaza_dos_variantes_activas_iguales_del_mismo_producto(
    connection: Connection,
) -> None:
    _insert_coffee(connection)
    connection.execute(INSERT_VARIANT, {"kind": "peso", "price": None, "active": False})
    connection.execute(INSERT_VARIANT, {"kind": "peso", "price": None, "active": True})

    with pytest.raises(IntegrityError):
        connection.execute(INSERT_VARIANT, {"kind": "peso", "price": 32000, "active": True})


def test_downgrade_elimina_las_tablas_del_catalogo(
    alembic_config: Config, connection: Connection
) -> None:
    command.downgrade(alembic_config, "base")

    tables = inspect(connection).get_table_names()
    assert "product" not in tables
    assert "product_variant" not in tables


# PED-16: tablas de cotización (data-model.md «Tablas nuevas»)

QUOTE_TABLES = ("quote", "quote_line")

INSERT_QUOTE = text(
    "INSERT INTO quote (id, status, customer_message, created_at, ai_outcome, "
    "delivery_date_needs_review, delivery_time_needs_review, delivery_mode, "
    "delivery_mode_needs_review) "
    "VALUES (1, :status, 'dos tortas', '2026-11-21 15:00:00', :ai_outcome, 0, 0, :mode, 0)"
)
VALID_QUOTE = {"status": "borrador", "ai_outcome": "ok", "mode": None}

INSERT_LINE = text(
    "INSERT INTO quote_line (quote_id, position, customer_text, status, review_reason, "
    "product_id, variant_id, label, unit_price, quantity, quantity_assumed) "
    "VALUES (1, 1, 'dos tortas', :status, :reason, :product_id, NULL, :label, :price, "
    ":quantity, 0)"
)
VALID_LINE = {
    "status": "lista",
    "reason": None,
    "product_id": 1,
    "label": "Café",
    "price": 18000,
    "quantity": 2,
}


def _require_quote_tables(connection: Connection) -> None:
    """Falla con una aserción clara si la migración de cotizaciones no se ha aplicado."""
    tables = inspect(connection).get_table_names()
    missing = [table for table in QUOTE_TABLES if table not in tables]
    assert missing == [], f"faltan las tablas {missing}"


def _insert_quote(connection: Connection, **overrides: object) -> None:
    _require_quote_tables(connection)
    connection.execute(INSERT_QUOTE, {**VALID_QUOTE, **overrides})


def _insert_quote_with_coffee(connection: Connection) -> None:
    _insert_coffee(connection)
    _insert_quote(connection)


def test_migraciones_crean_las_tablas_de_cotizacion(connection: Connection) -> None:
    _require_quote_tables(connection)


def test_una_cotizacion_y_una_linea_validas_se_guardan(connection: Connection) -> None:
    _insert_quote_with_coffee(connection)

    connection.execute(INSERT_LINE, VALID_LINE)

    assert connection.execute(text("SELECT count(*) FROM quote_line")).scalar_one() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "enviada"},
        {"ai_outcome": "desconocido"},
        {"mode": "envio"},
    ],
    ids=["estado", "resultado-de-la-ia", "modalidad"],
)
def test_la_base_rechaza_una_cotizacion_con_valores_fuera_del_dominio(
    connection: Connection, overrides: dict[str, object]
) -> None:
    _require_quote_tables(connection)

    with pytest.raises(IntegrityError):
        _insert_quote(connection, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "aprobada"},
        {"quantity": 0},
        {"quantity": 1000},
        {"price": 0},
        {"product_id": None},
        {"price": None},
        {"quantity": None},
        {"label": None},
        {"reason": "no_reconocido"},
        {"status": "por_revisar", "price": None, "label": None, "reason": None},
        {"status": "por_revisar", "price": 18000, "reason": "falta_variante"},
        {"status": "por_revisar", "price": None, "reason": "otro_motivo"},
    ],
    ids=[
        "estado-desconocido",
        "cantidad-cero",
        "cantidad-mayor-que-999",
        "precio-cero",
        "lista-sin-producto",
        "lista-sin-precio",
        "lista-sin-cantidad",
        "lista-sin-etiqueta",
        "lista-con-motivo",
        "por-revisar-sin-motivo",
        "por-revisar-con-precio",
        "motivo-desconocido",
    ],
)
def test_la_base_rechaza_una_linea_que_rompe_su_invariante(
    connection: Connection, overrides: dict[str, object]
) -> None:
    _insert_quote_with_coffee(connection)

    with pytest.raises(IntegrityError):
        connection.execute(INSERT_LINE, {**VALID_LINE, **overrides})


def test_una_linea_por_revisar_sin_producto_ni_precio_se_guarda(connection: Connection) -> None:
    _insert_quote_with_coffee(connection)

    connection.execute(
        INSERT_LINE,
        {
            "status": "por_revisar",
            "reason": "no_reconocido",
            "product_id": None,
            "label": None,
            "price": None,
            "quantity": None,
        },
    )

    assert connection.execute(text("SELECT count(*) FROM quote_line")).scalar_one() == 1


def test_las_claves_foraneas_de_las_lineas_tienen_sus_acciones(connection: Connection) -> None:
    # SQLite no aplica las claves foráneas sin PRAGMA; se verifica el esquema declarado, que es
    # el que PostgreSQL sí aplica en producción.
    _require_quote_tables(connection)

    actions = {
        fk["referred_table"]: fk["options"].get("ondelete")
        for fk in inspect(connection).get_foreign_keys("quote_line")
    }

    assert actions == {"quote": "CASCADE", "product": "RESTRICT", "product_variant": "RESTRICT"}


def test_la_lista_de_cotizaciones_tiene_indice_por_fecha(connection: Connection) -> None:
    _require_quote_tables(connection)

    indexed = [index["column_names"] for index in inspect(connection).get_indexes("quote")]

    assert ["created_at"] in indexed


def test_downgrade_de_un_paso_elimina_solo_las_tablas_de_cotizacion(
    alembic_config: Config, connection: Connection
) -> None:
    _require_quote_tables(connection)

    command.downgrade(alembic_config, "-1")

    tables = inspect(connection).get_table_names()
    assert not set(QUOTE_TABLES) & set(tables)
    assert "product" in tables
    assert "product_variant" in tables
