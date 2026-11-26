"""La siembra del catálogo de demostración al arrancar, según SEED_DEMO_CATALOG (PED-102)."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, select

from app.config import Settings
from app.models.catalog import Product


def _app(settings: Settings) -> FastAPI:
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    application = create_app(settings)
    # En producción las tablas las crea Alembic antes de arrancar; aquí, create_all.
    SQLModel.metadata.create_all(application.state.engine)
    return application


def test_con_la_variable_activa_el_arranque_siembra_el_catalogo(
    test_settings: Settings, app_log: pytest.LogCaptureFixture
) -> None:
    settings = test_settings.model_copy(update={"seed_demo_catalog": True})
    application = _app(settings)

    with TestClient(application):
        pass

    with Session(application.state.engine) as session:
        assert len(session.exec(select(Product)).all()) == 11
    assert any(
        record.getMessage().startswith("Catálogo de demostración:") for record in app_log.records
    )


def test_sin_la_variable_el_arranque_no_toca_la_base_ni_registra_nada(
    test_settings: Settings, app_log: pytest.LogCaptureFixture
) -> None:
    application = _app(test_settings)
    engine = application.state.engine
    statements: list[str] = []
    transactions: list[object] = []

    def on_execute(*args: Any) -> None:
        statements.append(str(args[2]))

    def on_begin(connection: object) -> None:
        transactions.append(connection)

    event.listen(engine, "before_cursor_execute", on_execute)
    event.listen(engine, "begin", on_begin)
    try:
        app_log.clear()
        with TestClient(application):
            pass
    finally:
        event.remove(engine, "before_cursor_execute", on_execute)
        event.remove(engine, "begin", on_begin)

    assert statements == []
    assert transactions == []
    assert not any("demostración" in record.getMessage() for record in app_log.records)
    with Session(engine) as session:
        assert session.exec(select(Product)).all() == []
