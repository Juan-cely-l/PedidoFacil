"""Pruebas de la configuración por ambiente (app/config.py)."""

from typing import Literal

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


# Historia 1: producción no arranca mal configurada

LOCAL_HINT = "Para desarrollo local copia .env.example a .env (ENVIRONMENT=local)"
VALID_POSTGRES_URL = "postgresql://usuario:clave@host/db"
VALID_SECRET_KEY = "k" * 32
LEAKED_DB_URL = "sqlite:///clave-secreta-db.db"
LEAKED_SHORT_VALUE = "clave-secreta-corta"
LEAKED_LONG_VALUE = "clave-de-produccion-de-32-caracteres"


def _set_production_env(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    """Define un ambiente de producción válido; cada override cambia (o borra, con None) una."""
    variables: dict[str, str | None] = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": VALID_POSTGRES_URL,
        "SECRET_KEY": VALID_SECRET_KEY,
        "AI_PROVIDER": "fake",
        "GEMINI_API_KEY": None,
    }
    variables.update(overrides)
    for name, value in variables.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def _configuration_error(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> str:
    """Construye Settings de producción y devuelve el mensaje del único error de configuración."""
    _set_production_env(monkeypatch, **overrides)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    errors = error.value.errors()
    assert len(errors) == 1
    return str(errors[0]["msg"])


def test_sin_environment_el_ambiente_es_produccion(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, ENVIRONMENT=None)

    assert Settings(_env_file=None).environment == "production"


def test_produccion_sin_database_url_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(monkeypatch, DATABASE_URL=None)

    assert "DATABASE_URL" in message
    assert "SECRET_KEY" not in message


def test_produccion_con_sqlite_exige_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(monkeypatch, DATABASE_URL="sqlite:///x.db")

    assert "DATABASE_URL" in message
    assert "PostgreSQL" in message


@pytest.mark.parametrize("url", ["postgresql://u:p@h/db", "postgres://u:p@h/db"])
def test_produccion_acepta_urls_de_postgresql(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    _set_production_env(monkeypatch, DATABASE_URL=url)

    assert Settings(_env_file=None).environment == "production"


def test_produccion_sin_secret_key_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(monkeypatch, SECRET_KEY=None)

    assert "SECRET_KEY" in message
    assert "DATABASE_URL" not in message


def test_produccion_rechaza_secret_key_de_31_caracteres(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(monkeypatch, SECRET_KEY="k" * 31)

    assert "SECRET_KEY" in message
    assert "32" in message


def test_produccion_acepta_secret_key_de_32_caracteres(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, SECRET_KEY="k" * 32)

    settings = Settings(_env_file=None)

    assert settings.secret_key is not None
    assert settings.secret_key.get_secret_value() == "k" * 32


def test_produccion_usa_gemini_por_defecto(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, AI_PROVIDER=None, GEMINI_API_KEY="clave-gemini")

    assert Settings(_env_file=None).ai_provider == "gemini"


def test_produccion_con_gemini_sin_clave_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(monkeypatch, AI_PROVIDER=None)

    assert "GEMINI_API_KEY" in message


def test_produccion_con_fake_no_exige_clave_de_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, AI_PROVIDER="fake", GEMINI_API_KEY=None)

    assert Settings(_env_file=None).ai_provider == "fake"


def test_un_proveedor_de_ia_no_admitido_lista_los_valores_validos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, AI_PROVIDER="openai")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    message = str(error.value)
    assert "'fake'" in message
    assert "'gemini'" in message


@pytest.mark.parametrize("environment", ["local", "test"])
def test_fuera_de_produccion_el_proveedor_de_ia_es_fake(
    monkeypatch: pytest.MonkeyPatch, environment: Literal["local", "test"]
) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    settings = Settings(_env_file=None, environment=environment)

    assert settings.ai_provider == "fake"


@pytest.mark.parametrize("environment", ["local", "test"])
def test_fuera_de_produccion_la_secret_key_se_genera(
    monkeypatch: pytest.MonkeyPatch, environment: Literal["local", "test"]
) -> None:
    monkeypatch.setenv("SECRET_KEY", "")

    first = Settings(_env_file=None, environment=environment)
    second = Settings(_env_file=None, environment=environment)

    assert first.secret_key is not None
    assert second.secret_key is not None
    assert len(first.secret_key.get_secret_value()) >= 32
    assert first.secret_key != second.secret_key


def test_una_database_url_vacia_cuenta_como_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")

    settings = Settings(_env_file=None, environment="local")

    assert _database_url(settings) == "sqlite:///./pedidofacil.db"


def test_produccion_con_secret_key_vacia_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(monkeypatch, SECRET_KEY="")

    assert "SECRET_KEY" in message


def test_produccion_nombra_todas_las_variables_faltantes_a_la_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, DATABASE_URL=None, SECRET_KEY=None, AI_PROVIDER=None)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    # Diseño (FR-007): un único error de configuración que nombra todas las variables,
    # no un error por variable. Por eso se exige exactamente uno y se revisa su mensaje.
    errors = error.value.errors()
    assert len(errors) == 1
    message = str(errors[0]["msg"])
    for variable in ("DATABASE_URL", "SECRET_KEY", "GEMINI_API_KEY"):
        assert variable in message


# Historia 1: los errores y la representación no exponen secretos


def test_el_error_no_muestra_valores_secretos(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(
        monkeypatch,
        DATABASE_URL=LEAKED_DB_URL,
        SECRET_KEY=LEAKED_SHORT_VALUE,
    )

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "clave-secreta" not in str(error.value)


def test_el_error_termina_con_la_sugerencia_para_desarrollo_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = _configuration_error(monkeypatch, DATABASE_URL=None)

    assert message.endswith(LOCAL_HINT)


def test_la_representacion_de_settings_oculta_los_secretos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, SECRET_KEY=LEAKED_LONG_VALUE)

    text = repr(Settings(_env_file=None))

    assert "clave-de-produccion" not in text
    assert "usuario:clave" not in text
    assert "secret_key=SecretStr('**********')" in text
