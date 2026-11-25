"""Privacidad en los logs de cotización (research R11, SC-006, FR-018).

El proveedor simulado repite el mensaje del cliente en sus errores, como puede hacerlo uno real:
así la prueba falla si alguien registra `str(error)` o su traza.
"""

import logging
import re
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.fallback import FallbackModel
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from app.db import build_engine
from app.dependencies import get_quote_extractor
from tests.doubles import (
    EMPTY_EXTRACTION,
    ReferenceCatalog,
    ScriptedModel,
    extraction_model,
    line_payload,
    quote_agent,
    raising_model,
    seed_reference_catalog,
    slow_model,
)

MESSAGE = "MENSAJE-CENTINELA dos cafes para DIRECCION-CENTINELA"
SENTINELS = ("MENSAJE-CENTINELA", "DIRECCION-CENTINELA")
LOGGER = "pedidofacil.quotes"


@pytest.fixture
def ref(auth_app: FastAPI) -> ReferenceCatalog:
    with Session(auth_app.state.engine) as session:
        return seed_reference_catalog(session)


@pytest.fixture
def log(auth_app: FastAPI, app_log: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    # Todo lo que se registre, también lo de las librerías y en DEBUG.
    app_log.set_level(logging.DEBUG)
    app_log.set_level(logging.DEBUG, logger="pedidofacil")
    yield app_log
    auth_app.dependency_overrides.pop(get_quote_extractor, None)


def _http_error(status_code: int) -> ScriptedModel:
    return raising_model(ModelHTTPError(status_code, "modelo-falso", body={"eco": MESSAGE}))


def _invalid_output() -> ScriptedModel:
    line = {**line_payload(1, None, 1, MESSAGE), "price": MESSAGE}
    return extraction_model({**EMPTY_EXTRACTION, "lines": [line]})


def _both_fail() -> FallbackModel:
    return FallbackModel(_http_error(503), _http_error(429), fallback_on=(ModelHTTPError,))


# id: (modelo, resultado, tipo de la excepción que se registra)
Failure = tuple[Callable[[], ScriptedModel | FallbackModel], str, str]
FAILURES: dict[str, Failure] = {
    "tiempo_agotado": (lambda: slow_model(1), "timeout", "TimeoutError"),
    "error_503": (lambda: _http_error(503), "provider_error", "ModelHTTPError"),
    "fallan_los_dos": (_both_fail, "provider_error", "FallbackExceptionGroup"),
    "salida_invalida": (_invalid_output, "invalid_output", "UnexpectedModelBehavior"),
}


def _quote_with(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    model: ScriptedModel | FallbackModel,
) -> int:
    settings = app.state.settings.model_copy(update={"ai_timeout_seconds": 0.2})
    monkeypatch.setattr(app.state, "settings", settings)
    agent = quote_agent(extraction_model(EMPTY_EXTRACTION))
    app.dependency_overrides[get_quote_extractor] = lambda: agent
    with agent.override(model=model):
        response = client.post("/cotizaciones", data={"message": MESSAGE}, follow_redirects=False)
    assert response.status_code == 303
    return int(response.headers["location"].rsplit("/", 1)[1])


def _assert_private(log: pytest.LogCaptureFixture) -> None:
    for sentinel in SENTINELS:
        assert sentinel not in log.text  # incluye las trazas que se hayan registrado
        for record in log.records:
            assert sentinel not in str(record.args)


@pytest.mark.parametrize("case", FAILURES.values(), ids=FAILURES.keys())
def test_cada_falla_deja_un_warning_con_resultado_tipo_y_duracion_sin_el_mensaje(
    client: TestClient,
    ref: ReferenceCatalog,
    log: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    case: Failure,
) -> None:
    build_model, outcome, error_type = case
    app = client.app
    assert isinstance(app, FastAPI)

    _quote_with(app, client, monkeypatch, build_model())

    (record,) = [r for r in log.records if r.name == LOGGER and r.levelno == logging.WARNING]
    text_logged = record.getMessage()
    assert f"resultado={outcome}" in text_logged
    assert f"error={error_type}" in text_logged
    assert re.search(r"duración=\d+ ms", text_logged)
    assert record.exc_info is None  # solo el tipo, sin traza
    _assert_private(log)


def test_el_exito_deja_una_linea_info_con_los_conteos_sin_el_mensaje(
    client: TestClient,
    ref: ReferenceCatalog,
    log: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lines = [line_payload(ref.cafe_id, None, 2, MESSAGE), line_payload(None, None, 1, MESSAGE)]
    model = extraction_model(
        {**EMPTY_EXTRACTION, "lines": lines, "delivery_address": "DIRECCION-CENTINELA"}
    )
    app = client.app
    assert isinstance(app, FastAPI)

    quote_id = _quote_with(app, client, monkeypatch, model)

    (record,) = [r for r in log.records if r.name == LOGGER]
    assert record.levelno == logging.INFO
    text_logged = record.getMessage()
    for field in (f"cotización={quote_id}", "resultado=ok", "líneas=2", "por revisar=1"):
        assert field in text_logged
    assert re.search(r"duración=\d+ ms", text_logged)
    _assert_private(log)


@pytest.mark.parametrize("url", ["sqlite://", "postgresql://usuario:clave@host/db"])
def test_el_motor_oculta_los_parametros_en_sus_errores(url: str) -> None:
    # Un fallo al guardar termina en una traza del servidor, y SQLAlchemy pone ahí los parámetros:
    # el mensaje y la dirección del cliente. Crear el motor no abre conexiones.
    assert build_engine(url).hide_parameters is True


def test_un_error_de_la_base_no_repite_el_mensaje_del_cliente() -> None:
    engine = build_engine("sqlite://")

    with engine.connect() as connection, pytest.raises(OperationalError) as caught:
        connection.execute(text("INSERT INTO nada VALUES (:mensaje)"), {"mensaje": MESSAGE})

    assert "MENSAJE-CENTINELA" not in str(caught.value)
