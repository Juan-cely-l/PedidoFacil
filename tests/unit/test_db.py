"""Pruebas del motor de base de datos (app/db.py), sin red."""

import threading
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session
from sqlmodel import create_engine as real_create_engine

from app import db
from app.db import build_engine


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@h/db",
        "postgres://u:p@h/db",
        "postgresql+psycopg://u:p@h/db",
    ],
)
def test_las_urls_de_postgresql_usan_psycopg(url: str) -> None:
    engine = build_engine(url)

    assert engine.url.drivername == "postgresql+psycopg"


def test_crear_el_motor_no_abre_conexiones() -> None:
    # Un host inexistente fallaría al conectar; crear el motor no debe intentarlo.
    engine = build_engine("postgresql://u:p@host-inexistente.invalid/db")

    assert engine.url.host == "host-inexistente.invalid"


def test_sqlite_en_memoria_se_puede_usar_desde_otro_hilo() -> None:
    engine = build_engine("sqlite://")
    results: list[int] = []

    def query() -> None:
        with Session(engine) as session:
            results.append(session.execute(text("SELECT 1")).scalar_one())

    worker = threading.Thread(target=query)
    worker.start()
    worker.join()

    assert results == [1]


def _spy_create_engine(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Sustituye create_engine en app.db por un espía que registra sus argumentos."""
    calls: list[dict[str, Any]] = []

    def spy(url: str, **kwargs: Any) -> Engine:
        calls.append(kwargs)
        return real_create_engine(url, **kwargs)

    monkeypatch.setattr(db, "create_engine", spy, raising=False)
    return calls


def test_postgresql_tiene_tiempo_limite_de_conexion_de_5_segundos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _spy_create_engine(monkeypatch)

    build_engine("postgresql://u:p@h/db")

    assert len(calls) == 1
    assert calls[0]["connect_args"] == {"connect_timeout": 5}
    assert calls[0]["pool_pre_ping"] is True


def test_sqlite_no_usa_tiempo_limite_de_conexion(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _spy_create_engine(monkeypatch)

    build_engine("sqlite://")

    assert len(calls) == 1
    assert "connect_timeout" not in calls[0].get("connect_args", {})


def test_sqlite_en_archivo_no_usa_una_unica_conexion_compartida(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'pedidofacil.db'}")

    assert not isinstance(engine.pool, StaticPool)
    with Session(engine) as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
