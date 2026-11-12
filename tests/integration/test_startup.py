"""Pruebas del arranque de la aplicación (create_app)."""

import logging

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

FAKE_PROVIDER_WARNING = "proveedor de IA simulado"


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "pedidofacil" and record.levelno == logging.WARNING
    ]


def test_create_app_guarda_la_configuracion_recibida(production_settings: Settings) -> None:
    application = create_app(production_settings)

    assert application.state.settings is production_settings


def test_produccion_con_ia_simulada_avisa_al_arrancar(
    production_settings: Settings, app_log: pytest.LogCaptureFixture
) -> None:
    create_app(production_settings)

    assert any(FAKE_PROVIDER_WARNING in message for message in _warnings(app_log))


def test_produccion_con_gemini_no_avisa_de_ia_simulada(
    monkeypatch: pytest.MonkeyPatch,
    production_settings: Settings,
    app_log: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-gemini")
    gemini_settings = Settings(_env_file=None)

    create_app(gemini_settings)

    assert not any(FAKE_PROVIDER_WARNING in message for message in _warnings(app_log))


def _app_handlers() -> list[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger("pedidofacil").handlers
        if handler.get_name() == "pedidofacil"
    ]


def test_el_logger_de_la_app_tiene_su_propio_handler_y_no_propaga(
    test_settings: Settings,
) -> None:
    # No depende de basicConfig: uvicorn y pytest ya instalan handlers en el logger raíz.
    create_app(test_settings)

    assert len(_app_handlers()) == 1
    assert logging.getLogger("pedidofacil").propagate is False


def test_crear_la_app_dos_veces_no_duplica_el_handler(test_settings: Settings) -> None:
    create_app(test_settings)
    create_app(test_settings)

    assert len(_app_handlers()) == 1


def test_create_app_aplica_el_nivel_de_log_al_logger_de_la_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    local_settings = Settings(
        _env_file=None, environment="local", database_url=SecretStr("sqlite://")
    )

    create_app(local_settings)

    assert logging.getLogger("pedidofacil").getEffectiveLevel() == logging.DEBUG


def test_create_app_en_produccion_registra_desde_info(production_settings: Settings) -> None:
    create_app(production_settings)

    assert logging.getLogger("pedidofacil").getEffectiveLevel() == logging.INFO
