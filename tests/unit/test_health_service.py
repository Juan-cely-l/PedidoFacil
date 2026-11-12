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


def test_la_base_caida_devuelve_false(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="pedidofacil"):
        assert check_database(FailingSession()) is False

    assert any(record.levelno >= logging.WARNING for record in caplog.records)


def test_el_log_de_la_falla_no_contiene_credenciales(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        check_database(FailingSession())

    assert "usuario:clave" not in caplog.text
    assert "postgresql://" not in caplog.text
