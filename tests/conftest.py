"""Configuración común de las pruebas.

ENVIRONMENT se fija en "test" antes de que cualquier prueba importe `app`, para que la
configuración nunca lea el `.env` del desarrollador ni use valores de otro ambiente.
"""

import logging
import os
from collections.abc import Iterator

import pytest

# app.config no tiene efectos al importarse; app.main sí (crea la app), por eso ninguna prueba
# lo importa a nivel de módulo antes de que se fije ENVIRONMENT aquí.
from app.config import Settings

os.environ["ENVIRONMENT"] = "test"


@pytest.fixture(autouse=True)
def restore_app_log_level() -> Iterator[None]:
    """Restaura el nivel del logger de la app: `create_app` lo cambia y es estado global."""
    app_logger = logging.getLogger("pedidofacil")
    previous_level = app_logger.level
    yield
    app_logger.setLevel(previous_level)


@pytest.fixture
def test_settings() -> Settings:
    """Configuración del ambiente de pruebas, sin leer ningún archivo .env."""
    return Settings(_env_file=None, environment="test")
