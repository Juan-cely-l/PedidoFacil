"""Atributos de la cookie de sesión (constitución VI, research.md R5).

Starlette marca la cookie como HttpOnly por su cuenta; igual se verifica en la cabecera para no
darlo por hecho.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.db import get_session
from app.services.identity import get_identity_provider
from tests.doubles import SESSION_COOKIE, FailingSession, FakeIdentityProvider, log_in


def _session_cookie_header(client: TestClient) -> str:
    """Cabecera Set-Cookie de la sesión en la respuesta del callback de Google."""
    callback = log_in(client)
    headers = [
        value
        for value in callback.headers.get_list("set-cookie")
        if value.startswith(f"{SESSION_COOKIE}=")
    ]
    assert len(headers) == 1, callback.headers
    return headers[0].lower()


def _attributes(header: str) -> set[str]:
    return {part.strip() for part in header.split(";")[1:]}


def _failing_session() -> Iterator[Session]:
    """Base caída: la app de producción nunca intenta conectarse a PostgreSQL en las pruebas."""
    yield FailingSession()


@pytest.fixture
def production_client(
    production_settings: Settings, identity_provider: FakeIdentityProvider
) -> Iterator[TestClient]:
    """App configurada como producción, sin red: base y proveedor sustituidos."""
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    application = create_app(production_settings)
    application.dependency_overrides[get_session] = _failing_session
    application.dependency_overrides[get_identity_provider] = lambda: identity_provider
    with TestClient(application) as client:
        yield client


def test_la_cookie_de_sesion_es_httponly_samesite_lax_y_dura_12_horas(
    anonymous_client: TestClient,
) -> None:
    attributes = _attributes(_session_cookie_header(anonymous_client))

    assert "httponly" in attributes
    assert "samesite=lax" in attributes
    assert "max-age=43200" in attributes
    assert "path=/" in attributes


def test_fuera_de_produccion_la_cookie_no_exige_https(anonymous_client: TestClient) -> None:
    assert "secure" not in _attributes(_session_cookie_header(anonymous_client))


def test_en_produccion_la_cookie_solo_viaja_por_https(production_client: TestClient) -> None:
    attributes = _attributes(_session_cookie_header(production_client))

    assert "secure" in attributes
    assert "httponly" in attributes
    assert "samesite=lax" in attributes
