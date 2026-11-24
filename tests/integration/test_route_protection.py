"""Denegar por defecto: ninguna ruta de gestión responde sin sesión (research.md R1 y R2).

La prueba recorre `app.routes` de la app configurada como producción, donde no existe la
documentación automática (R13), así que no hay excepciones. Falla si alguien agrega una ruta
a `PUBLIC_PATHS` sin agregarla aquí, si monta una ruta fuera del mecanismo de dependencias o si
quita la dependencia global.

FastAPI 0.162 guarda los routers incluidos envueltos (`_IncludedRouter`), así que `app.routes`
no expone las `APIRoute`. Las rutas efectivas se recorren con `fastapi.routing.iter_route_contexts`,
que da cada ruta con su path completo y su ruta original.
"""

import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.db import get_session
from app.security import PUBLIC_PATHS
from app.services.identity import get_identity_provider
from tests.doubles import FailingSession, FakeIdentityProvider

# Duplicada a propósito: ampliar lo público exige tocar dos sitios.
EXPECTED_PUBLIC = {
    "/health",
    "/health/live",
    "/login",
    "/login/google",
    "/auth/google/callback",
    # PED-93: Telegram no tiene sesión; lo protege su token secreto (constitución, principio VI).
    "/telegram/webhook",
}


def _failing_session() -> Iterator[Session]:
    """Base caída: la app de producción nunca intenta conectarse a PostgreSQL."""
    yield FailingSession()


@pytest.fixture
def production_app(production_settings: Settings) -> FastAPI:
    """App de producción sin red: base y proveedor de identidad sustituidos."""
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    provider = FakeIdentityProvider()
    application = create_app(production_settings)
    application.dependency_overrides[get_session] = _failing_session
    application.dependency_overrides[get_identity_provider] = lambda: provider
    return application


def _routes(application: FastAPI) -> list[RouteContext]:
    """Todas las rutas efectivas de la app, incluidas las de los routers."""
    return list(iter_route_contexts(application.routes))


def _api_routes(application: FastAPI) -> list[tuple[str, str]]:
    """(método, path) de cada APIRoute, sin HEAD (lo agrega Starlette a cada GET)."""
    return [
        (method, context.path or "")
        for context in _routes(application)
        if isinstance(context.original_route, APIRoute)
        for method in sorted((context.methods or set()) - {"HEAD"})
    ]


def _concrete_path(path: str) -> str:
    """Reemplaza cada parámetro de la ruta ({product_id}) por un valor válido."""
    return re.sub(r"\{[^}]+\}", "1", path)


def test_la_lista_de_rutas_publicas_es_la_esperada() -> None:
    assert set(PUBLIC_PATHS) == EXPECTED_PUBLIC


def test_toda_ruta_pasa_por_el_mecanismo_de_dependencias(production_app: FastAPI) -> None:
    # Las rutas que no son APIRoute (add_route, mount, StaticFiles, documentación) no ejecutan
    # require_owner: en producción no debe haber ninguna.
    outside = [
        context.path or repr(context.original_route)
        for context in _routes(production_app)
        if not isinstance(context.original_route, APIRoute)
    ]

    assert outside == []


def test_sin_sesion_toda_ruta_no_publica_redirige_al_login(production_app: FastAPI) -> None:
    client = TestClient(production_app, raise_server_exceptions=False)
    routes = [(m, p) for m, p in _api_routes(production_app) if p not in EXPECTED_PUBLIC]
    unprotected: list[str] = []

    for method, path in routes:
        response = client.request(method, _concrete_path(path), follow_redirects=False)
        location = response.headers.get("location", "")
        if response.status_code != 303 or not location.startswith("/login"):
            unprotected.append(f"{method} {path} → {response.status_code} {location}")

    # Que el recorrido encuentre rutas: si FastAPI cambiara cómo las expone, la prueba no
    # debe pasar en vacío.
    assert ("GET", "/productos") in routes
    assert unprotected == []


def test_sin_sesion_las_rutas_publicas_no_redirigen_al_login(production_app: FastAPI) -> None:
    client = TestClient(production_app, raise_server_exceptions=False)
    routes = [(m, p) for m, p in _api_routes(production_app) if p in EXPECTED_PUBLIC]
    redirected: list[str] = []

    for method, path in routes:
        response = client.request(method, path, follow_redirects=False)
        if response.headers.get("location", "").startswith("/login"):
            redirected.append(f"{method} {path}")

    assert {path for _, path in routes} == EXPECTED_PUBLIC
    assert redirected == []
