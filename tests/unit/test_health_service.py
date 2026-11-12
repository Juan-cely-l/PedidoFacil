"""Pruebas del servicio de salud (app/services/health.py), sin HTTP ni red."""

import logging

import pytest
from sqlmodel import Session, create_engine

from app.services.health import check_database
from tests.doubles import FailingSession


def test_la_base_responde() -> None:
    engine = create_engine("sqlite://")

    with Session(engine) as session:
        assert check_database(session) is True


def test_la_base_caida_devuelve_false(app_log: pytest.LogCaptureFixture) -> None:
    with app_log.at_level(logging.WARNING, logger="pedidofacil"):
        assert check_database(FailingSession()) is False

    assert any(record.levelno >= logging.WARNING for record in app_log.records)


def test_el_log_de_la_falla_no_contiene_credenciales(app_log: pytest.LogCaptureFixture) -> None:
    with app_log.at_level(logging.DEBUG, logger="pedidofacil"):
        check_database(FailingSession())

    # Se registró algo (si no, la prueba no verificaría nada) y no contiene credenciales.
    assert app_log.records
    assert "usuario:clave" not in app_log.text
    assert "postgresql://" not in app_log.text
