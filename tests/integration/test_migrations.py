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


def test_downgrade_elimina_las_tablas_del_catalogo(
    alembic_config: Config, connection: Connection
) -> None:
    command.downgrade(alembic_config, "base")

    assert "product" not in inspect(connection).get_table_names()
