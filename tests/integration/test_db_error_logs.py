"""Un error de la base se registra por sus tipos y su ruta, nunca por su texto (FR-018, R11).

`hide_parameters` no basta: PostgreSQL agrega un `DETAIL` con la fila completa. Si la excepción
llega sin capturar al servidor, uvicorn imprime su traza con ese texto. El cliente de pruebas
vuelve a lanzar lo que quede sin capturar, así que estas pruebas fallan si la excepción escapa.

El manejador atrapa solo lo de SQLAlchemy y se porta igual en todos los ambientes.
"""

import logging
from collections.abc import Iterator
from typing import NoReturn

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import errors as pg
from sqlalchemy.exc import DataError, IntegrityError, PendingRollbackError
from sqlmodel import Session

from app.config import Settings
from app.db import get_session
from app.repositories import quotes as repository
from app.security import require_owner
from tests.doubles import LEAKY_DB_ERROR, FailingSession, seed_reference_catalog

MESSAGE = "MENSAJE-CENTINELA un cafe para DIRECCION-CENTINELA"
SENTINELS = ("MENSAJE-CENTINELA", "DIRECCION-CENTINELA")
DETAIL = f"DETAIL:  Failing row contains (1, borrador, {MESSAGE})."
NOTICE = "No pudimos completar la operación. Inténtalo de nuevo"


@pytest.fixture
def log(app_log: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    app_log.set_level(logging.DEBUG)  # todo, también lo de las librerías
    return app_log


def _failing_session() -> Iterator[Session]:
    yield FailingSession()


def _fail_on_save(app: FastAPI, monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    with Session(app.state.engine) as session:
        seed_reference_catalog(session)

    def failing_save(*_args: object) -> NoReturn:
        raise error

    monkeypatch.setattr(repository, "save_quote", failing_save)


def _assert_safe_line(log: pytest.LogCaptureFixture, *fields: str) -> None:
    (record,) = [record for record in log.records if record.levelno >= logging.ERROR]
    assert record.name.startswith("pedidofacil")
    for field in fields:
        assert field in record.getMessage()
    assert record.exc_info is None  # sin traza: la traza incluye el texto


def _assert_no_leaks(log: pytest.LogCaptureFixture, body: str = "") -> None:
    for secret in (*SENTINELS, "Failing row", LEAKY_DB_ERROR):
        assert secret not in log.text
        assert secret not in body
        for record in log.records:
            assert secret not in str(record.args)


@pytest.mark.parametrize(
    ("error", "name", "origin"),
    [
        pytest.param(
            IntegrityError("INSERT INTO quote", {}, pg.CheckViolation(DETAIL)),
            "IntegrityError",
            "psycopg.errors.CheckViolation",
            id="check",
        ),
        pytest.param(
            DataError("INSERT INTO quote", {}, pg.StringDataRightTruncation(DETAIL)),
            "DataError",
            "psycopg.errors.StringDataRightTruncation",
            id="dato_invalido",
        ),
        # No todo error de SQLAlchemy viene del driver.
        pytest.param(
            PendingRollbackError(DETAIL), "PendingRollbackError", "ninguno", id="sin_driver"
        ),
    ],
)
def test_un_fallo_al_guardar_registra_los_tipos_y_la_ruta_sin_el_texto(  # noqa: PLR0913, PLR0917
    client: TestClient,
    auth_app: FastAPI,
    log: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    name: str,
    origin: str,
) -> None:
    _fail_on_save(auth_app, monkeypatch, error)

    response = client.post("/cotizaciones", data={"message": MESSAGE})

    assert response.status_code == 500
    assert NOTICE in response.text
    _assert_safe_line(log, f"error={name}", f"origen={origin}", "ruta=POST /cotizaciones")
    _assert_no_leaks(log, response.text)


@pytest.mark.parametrize("environment", ["test", "local", "production"])
def test_con_la_base_caida_se_porta_igual_en_todos_los_ambientes(
    request: pytest.FixtureRequest, log: pytest.LogCaptureFixture, environment: str
) -> None:
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    settings: Settings
    if environment == "production":
        settings = request.getfixturevalue("production_settings")
    else:
        test_settings: Settings = request.getfixturevalue("test_settings")
        update = {"environment": environment, "log_level": "DEBUG"}
        settings = test_settings.model_copy(update=update)
    application = create_app(settings)
    application.dependency_overrides[get_session] = _failing_session
    application.dependency_overrides[require_owner] = lambda: None
    # La consulta de la URL no se registra: puede traer lo que sea.
    response = TestClient(application).get("/productos?nota=MENSAJE-CENTINELA")

    assert response.status_code == 500
    assert NOTICE in response.text
    _assert_safe_line(
        log, "error=OperationalError", "origen=builtins.Exception", "ruta=GET /productos"
    )
    # httpx registra la URL que pidió la prueba: solo cuenta lo que registra el servidor.
    for record in log.records:
        if record.name.startswith("pedidofacil"):
            assert "MENSAJE-CENTINELA" not in record.getMessage()
    assert LEAKY_DB_ERROR not in log.text
    assert LEAKY_DB_ERROR not in response.text


@pytest.mark.parametrize(
    "error",
    [ValueError("bug"), RuntimeError("bug"), KeyError("bug")],
    ids=lambda e: type(e).__name__,
)
def test_un_error_de_programacion_no_lo_captura_el_manejador(
    client: TestClient,
    auth_app: FastAPI,
    log: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    _fail_on_save(auth_app, monkeypatch, error)

    with pytest.raises(type(error)):
        client.post("/cotizaciones", data={"message": "un cafe"})

    assert [record for record in log.records if record.levelno >= logging.ERROR] == []
