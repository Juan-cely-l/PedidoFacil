"""Pruebas de la configuración por ambiente (app/config.py)."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def _database_url(settings: Settings) -> str:
    assert settings.database_url is not None
    return settings.database_url.get_secret_value()


def test_en_test_la_base_por_defecto_es_sqlite_en_memoria() -> None:
    settings = Settings(_env_file=None, environment="test")

    assert _database_url(settings) == "sqlite://"


def test_en_local_la_base_por_defecto_es_un_archivo_sqlite() -> None:
    settings = Settings(_env_file=None, environment="local")

    assert _database_url(settings) == "sqlite:///./pedidofacil.db"


def test_una_database_url_explicita_se_respeta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./otra.db")

    settings = Settings(_env_file=None, environment="local")

    assert _database_url(settings) == "sqlite:///./otra.db"


def test_un_ambiente_no_admitido_lista_los_valores_validos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    message = str(error.value)
    for allowed in ("'test'", "'local'", "'production'"):
        assert allowed in message
