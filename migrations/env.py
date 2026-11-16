"""Entorno de Alembic: decide sobre qué conexión se ejecutan las migraciones.

- Si quien invoca pasa una conexión en `config.attributes["connection"]` (las pruebas, con
  SQLite en memoria), se usa esa.
- Si no, la URL sale de la configuración de la app (`DATABASE_URL` según `ENVIRONMENT`) y el
  motor se crea con `build_engine`, igual que en la app (driver psycopg y tiempo límite).
"""

from logging.config import fileConfig
from typing import cast

from alembic import context
from pydantic import SecretStr
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

import app.models  # noqa: F401  (registra las tablas en SQLModel.metadata)
from app.config import get_settings
from app.db import build_engine

config = context.config
target_metadata = SQLModel.metadata


def run_migrations(connection: Connection) -> None:
    """Ejecuta las migraciones sobre una conexión abierta."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite no admite la mayoría de ALTER TABLE: Alembic recrea la tabla en lote.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Usa la conexión recibida o crea una a partir de la configuración de la app."""
    given = config.attributes.get("connection")
    if given is not None:
        run_migrations(given)
        return

    if config.config_file_name is not None:
        # Sin desactivar los loggers de la app que ya existan.
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    database_url = cast(SecretStr, get_settings().database_url).get_secret_value()
    engine = build_engine(database_url)
    with engine.connect() as connection:
        run_migrations(connection)
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Las migraciones en modo offline (--sql) no están soportadas.")
run_migrations_online()
