"""Pruebas de la configuración por ambiente (app/config.py)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings, get_settings


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
VALID_GOOGLE_CLIENT_ID = "1234-abc.apps.googleusercontent.com"
VALID_GOOGLE_CLIENT_SECRET = "secreto-de-google"  # noqa: S105  (valor ficticio de prueba)
PRODUCTION_BASE_URL = "https://pedidofacil-6nky.onrender.com"
# Valor reconocible para comprobar que el secreto nunca aparece en errores ni en repr().
GOOGLE_SECRET_SENTINEL = "secreto-centinela"  # noqa: S105


def _set_production_env(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
    """Define un ambiente de producción válido; cada override cambia (o borra, con None) una."""
    variables: dict[str, str | None] = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": VALID_POSTGRES_URL,
        "SECRET_KEY": VALID_SECRET_KEY,
        "AI_PROVIDER": "fake",
        "GEMINI_API_KEY": None,
        # Login con Google (PED-15).
        "GOOGLE_CLIENT_ID": VALID_GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": VALID_GOOGLE_CLIENT_SECRET,
        "OWNER_EMAILS": "dueno@example.com",
        "PUBLIC_BASE_URL": PRODUCTION_BASE_URL,
        "RENDER_EXTERNAL_URL": None,
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


# Historia 3: en test la configuración no lee el archivo .env


@pytest.fixture
def project_with_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Directorio de trabajo con un .env propio y la caché de get_settings() limpia."""
    (tmp_path / ".env").write_text("LOG_LEVEL=ERROR\nAI_PROVIDER=gemini\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_en_test_get_settings_ignora_el_archivo_env(
    project_with_env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")

    settings = get_settings()

    assert settings.log_level != "ERROR"
    assert settings.ai_provider == "fake"


def test_en_local_get_settings_lee_el_archivo_env(
    project_with_env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")

    settings = get_settings()

    assert settings.log_level == "ERROR"
    assert settings.ai_provider == "gemini"


def test_en_local_una_variable_del_proceso_gana_al_archivo_env(
    project_with_env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    assert get_settings().log_level == "WARNING"


# Historia 4: nivel de log por defecto según el ambiente


@pytest.mark.parametrize(
    ("environment", "expected"),
    [("local", "DEBUG"), ("test", "INFO"), ("production", "INFO")],
)
def test_nivel_de_log_por_defecto_segun_el_ambiente(
    monkeypatch: pytest.MonkeyPatch,
    environment: Literal["local", "test", "production"],
    expected: str,
) -> None:
    _set_production_env(monkeypatch, ENVIRONMENT=environment, LOG_LEVEL=None)

    assert Settings(_env_file=None).log_level == expected


@pytest.mark.parametrize("environment", ["local", "test", "production"])
def test_un_log_level_explicito_se_respeta_en_todo_ambiente(
    monkeypatch: pytest.MonkeyPatch, environment: Literal["local", "test", "production"]
) -> None:
    _set_production_env(monkeypatch, ENVIRONMENT=environment, LOG_LEVEL="WARNING")

    assert Settings(_env_file=None).log_level == "WARNING"


# Login con Google (PED-15, T002)


def test_owner_emails_se_normalizan_y_descartan_los_vacios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OWNER_EMAILS", " Dueno@Gmail.com , otro@x.co ,,")

    settings = Settings(_env_file=None, environment="test")

    assert settings.owner_emails == frozenset({"dueno@gmail.com", "otro@x.co"})


def test_sin_owner_emails_la_lista_queda_vacia_fuera_de_produccion() -> None:
    settings = Settings(_env_file=None, environment="local")

    assert settings.owner_emails == frozenset()


@pytest.mark.parametrize(
    ("environment", "expected"),
    [("local", "http://127.0.0.1:8000"), ("test", "http://testserver")],
)
def test_public_base_url_por_defecto_segun_el_ambiente(
    environment: Literal["local", "test"], expected: str
) -> None:
    settings = Settings(_env_file=None, environment=environment)

    assert settings.public_base_url == expected


def test_public_base_url_explicita_se_respeta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")

    settings = Settings(_env_file=None, environment="local")

    assert settings.public_base_url == "http://localhost:8000"


def test_produccion_sin_public_base_url_usa_la_url_que_define_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, PUBLIC_BASE_URL=None, RENDER_EXTERNAL_URL=PRODUCTION_BASE_URL)

    settings = Settings(_env_file=None)

    assert settings.public_base_url == PRODUCTION_BASE_URL


def test_public_base_url_gana_a_la_url_de_render(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch, RENDER_EXTERNAL_URL="https://otra.onrender.com")

    settings = Settings(_env_file=None)

    assert settings.public_base_url == PRODUCTION_BASE_URL


@pytest.mark.parametrize(
    "variable", ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "OWNER_EMAILS", "PUBLIC_BASE_URL"]
)
def test_produccion_sin_variable_del_login_no_arranca(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    message = _configuration_error(monkeypatch, **{variable: None})

    assert variable in message


def test_produccion_con_owner_emails_solo_comas_no_arranca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = _configuration_error(monkeypatch, OWNER_EMAILS=" , ,")

    assert "OWNER_EMAILS" in message


def test_produccion_exige_public_base_url_con_https(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _configuration_error(
        monkeypatch, PUBLIC_BASE_URL="http://pedidofacil-6nky.onrender.com"
    )

    assert "PUBLIC_BASE_URL" in message
    assert "https://" in message


def test_produccion_con_el_login_completo_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_production_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.google_client_id == VALID_GOOGLE_CLIENT_ID
    assert settings.owner_emails == frozenset({"dueno@example.com"})


def test_el_error_no_muestra_el_secreto_de_google(monkeypatch: pytest.MonkeyPatch) -> None:
    # Falta OWNER_EMAILS para que haya error; el secreto presente no debe aparecer en él.
    _set_production_env(monkeypatch, GOOGLE_CLIENT_SECRET=GOOGLE_SECRET_SENTINEL, OWNER_EMAILS=None)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert GOOGLE_SECRET_SENTINEL not in str(error.value)


def test_la_representacion_de_settings_oculta_el_secreto_de_google(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, GOOGLE_CLIENT_SECRET=GOOGLE_SECRET_SENTINEL)

    settings = Settings(_env_file=None)
    secret = settings.google_client_secret

    # Primero el tipo: si el campo se declarara como str, repr() lo mostraría tal cual.
    assert isinstance(secret, SecretStr)
    assert secret.get_secret_value() == GOOGLE_SECRET_SENTINEL
    assert GOOGLE_SECRET_SENTINEL not in repr(settings)


def test_la_uri_de_vuelta_de_google_sale_de_public_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = Settings(_env_file=None, environment="test")
    _set_production_env(monkeypatch)
    production = Settings(_env_file=None)

    assert production.oauth_redirect_uri == (
        "https://pedidofacil-6nky.onrender.com/auth/google/callback"
    )
    assert local.oauth_redirect_uri == "http://testserver/auth/google/callback"


# PED-16: modelo de Gemini y tiempo de espera de la IA (contracts/configuration.md)


def test_el_modelo_el_respaldo_y_el_tiempo_de_espera_tienen_valores_por_defecto() -> None:
    settings = Settings(_env_file=None, environment="test")

    assert settings.gemini_model == "gemini-3.5-flash-lite"
    # Sin respaldo por defecto: la medición descartó gemini-3.8-flash (research R2).
    assert settings.gemini_fallback_model is None
    assert settings.ai_timeout_seconds == 10


@pytest.mark.parametrize("value", ["ninguno", " Ninguno "])
def test_el_respaldo_se_desactiva_con_ninguno(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", value)

    settings = Settings(_env_file=None, environment="test")

    assert settings.gemini_fallback_model is None


def test_un_respaldo_vacio_cuenta_como_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    # Convención del proyecto (env_ignore_empty): una variable vacía toma el valor por defecto.
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")

    settings = Settings(_env_file=None, environment="test")

    assert settings.gemini_fallback_model is None  # el valor por defecto: sin respaldo


def test_el_respaldo_no_puede_ser_el_mismo_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, environment="test")

    assert "GEMINI_FALLBACK_MODEL" in str(error.value)


def test_el_modelo_no_puede_quedar_en_blanco(monkeypatch: pytest.MonkeyPatch) -> None:
    # Vacío cuenta como ausente (valor por defecto); solo espacios sí llega a la validación.
    monkeypatch.setenv("GEMINI_MODEL", "   ")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="test")


@pytest.mark.parametrize("environment", ["local", "test"])
@pytest.mark.parametrize("timeout", ["0", "-1", "15.01"])
def test_el_tiempo_de_espera_fuera_de_rango_impide_arrancar(
    monkeypatch: pytest.MonkeyPatch, environment: Literal["local", "test"], timeout: str
) -> None:
    # Principio V: respaldo manual si la IA tarda más de 15 s; nunca se configura un tope mayor.
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment=environment)


def test_en_produccion_un_tiempo_de_espera_mayor_que_15_impide_arrancar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_production_env(monkeypatch, AI_TIMEOUT_SECONDS="15.01")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(("timeout", "expected"), [("15", 15.0), ("0.5", 0.5)])
def test_el_tiempo_de_espera_dentro_del_tope_se_acepta(
    monkeypatch: pytest.MonkeyPatch, timeout: str, expected: float
) -> None:
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", timeout)

    settings = Settings(_env_file=None, environment="test")

    assert settings.ai_timeout_seconds == expected


# Cobertura de ramas ya existentes de app/config.py (T010): no es comportamiento nuevo.


def test_un_respaldo_none_explicito_queda_sin_respaldo() -> None:
    settings = Settings(_env_file=None, environment="test", gemini_fallback_model=None)

    assert settings.gemini_fallback_model is None


def test_un_respaldo_en_blanco_impide_arrancar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "   ")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, environment="test")

    assert "GEMINI_FALLBACK_MODEL" in str(error.value)


# PED-93: bot de Telegram (specs/005-bot-telegram/spec.md, D2)


def test_el_bot_de_telegram_lee_sus_tres_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token-falso")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "secreto-falso")
    monkeypatch.setenv("OWNER_TELEGRAM_CHAT_ID", "987654321")

    settings = Settings(_env_file=None, environment="test")

    token = settings.telegram_bot_token  # type: ignore[attr-defined]
    secret = settings.telegram_webhook_secret  # type: ignore[attr-defined]
    assert isinstance(token, SecretStr)
    assert token.get_secret_value() == "123456:token-falso"
    assert isinstance(secret, SecretStr)
    assert secret.get_secret_value() == "secreto-falso"
    assert settings.owner_telegram_chat_id == 987654321  # type: ignore[attr-defined]
    assert settings.telegram_enabled is True  # type: ignore[attr-defined]


@pytest.mark.parametrize("environment", ["test", "production"])
def test_sin_variables_de_telegram_el_bot_queda_apagado_y_la_app_arranca(
    request: pytest.FixtureRequest, environment: str
) -> None:
    settings: Settings = (
        request.getfixturevalue("production_settings")
        if environment == "production"
        else Settings(_env_file=None, environment="test")
    )

    assert settings.telegram_bot_token is None  # type: ignore[attr-defined]
    assert settings.telegram_webhook_secret is None  # type: ignore[attr-defined]
    assert settings.owner_telegram_chat_id is None  # type: ignore[attr-defined]
    assert settings.telegram_enabled is False  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "variable", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "OWNER_TELEGRAM_CHAT_ID"]
)
def test_una_variable_de_telegram_vacia_cuenta_como_ausente(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "")

    settings = Settings(_env_file=None, environment="test")

    assert getattr(settings, variable.lower()) is None


@pytest.mark.parametrize(
    ("token", "secret"), [("123456:token-falso", None), (None, "secreto-falso")]
)
def test_el_bot_solo_se_activa_con_token_y_secreto(
    monkeypatch: pytest.MonkeyPatch, token: str | None, secret: str | None
) -> None:
    for name, value in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_WEBHOOK_SECRET", secret)):
        if value is not None:
            monkeypatch.setenv(name, value)

    settings = Settings(_env_file=None, environment="test")

    assert settings.telegram_enabled is False  # type: ignore[attr-defined]


def test_un_chat_del_dueno_que_no_es_un_numero_impide_arrancar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OWNER_TELEGRAM_CHAT_ID", "dueno")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, environment="test")

    assert "owner_telegram_chat_id" in str(error.value)
