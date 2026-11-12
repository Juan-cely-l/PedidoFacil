"""Configuración común de las pruebas.

ENVIRONMENT se fija en "test" antes de que cualquier prueba importe `app`, para que la
configuración nunca lea el `.env` del desarrollador ni use valores de otro ambiente.
"""

import logging
import os
from collections.abc import Iterator

import pytest

os.environ["ENVIRONMENT"] = "test"


@pytest.fixture(autouse=True)
def restore_app_log_level() -> Iterator[None]:
    """Restaura el nivel del logger de la app: `create_app` lo cambia y es estado global."""
    app_logger = logging.getLogger("pedidofacil")
    previous_level = app_logger.level
    yield
    app_logger.setLevel(previous_level)
