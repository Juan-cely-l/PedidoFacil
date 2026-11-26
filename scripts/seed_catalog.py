"""Siembra a mano el catálogo de demostración en la base que indique el entorno (PED-102).

Uso: uv run python -m scripts.seed_catalog

La conexión sale de la configuración de la app (DATABASE_URL o el SQLite local por defecto);
el script no recibe credenciales ni las escribe. La lógica vive en app/services/seed_catalog.py.
"""

import logging
from typing import cast

from pydantic import SecretStr

from app.config import get_settings
from app.db import build_engine
from app.services.seed_catalog import run_seed


def main() -> None:
    """Siembra y deja el resumen en la salida estándar."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    engine = build_engine(cast(SecretStr, settings.database_url).get_secret_value())
    try:
        run_seed(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
