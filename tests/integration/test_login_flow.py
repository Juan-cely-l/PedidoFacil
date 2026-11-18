"""Flujo de acceso del dueño con el proveedor de identidad simulado (nunca se llama a Google)."""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlmodel import SQLModel

from app.config import Settings
from app.services.identity import LoginFailed, VerifiedIdentity, get_identity_provider
from tests.doubles import (
    TOKEN_SENTINEL,
    ExplodingIdentityProvider,
    FakeIdentityProvider,
    log_in,
    read_session,
)

SECRET_KEY = "s" * 32  # la misma de la fixture test_settings
LOGIN_FAILED_MESSAGE = "No se pudo iniciar sesión con Google. Intenta de nuevo"
NOT_AUTHORIZED_MESSAGE = "Esta cuenta de Google no tiene acceso a PedidoFácil"
CANCELLED_MESSAGE = "No se completó el inicio de sesión con Google"
INTRUDER = VerifiedIdentity(email="intruso@gmail.com", email_verified=True, name="Intruso")
UNVERIFIED_OWNER = VerifiedIdentity(email="dueno@example.com", email_verified=False, name="Dueño")


# Historia 1: entrar con la cuenta de Google (T009)


def test_la_pagina_de_login_ofrece_entrar_con_google_y_no_pide_contrasena(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get("/login")

    assert response.status_code == 200
    assert "Entrar con Google" in response.text
    assert 'href="/login/google' in response.text
    assert 'type="password"' not in response.text


def test_entrar_lleva_a_la_pagina_que_se_queria_abrir(anonymous_client: TestClient) -> None:
    callback = log_in(anonymous_client, next_path="/productos/7")

    assert callback.status_code == 303
    assert callback.headers["location"] == "/productos/7"


def test_sin_destino_al_entrar_se_va_al_catalogo(anonymous_client: TestClient) -> None:
    callback = log_in(anonymous_client)

    assert callback.status_code == 303
    assert callback.headers["location"] == "/productos"


def test_un_destino_externo_se_ignora_y_se_va_al_catalogo(
    anonymous_client: TestClient,
) -> None:
    callback = log_in(anonymous_client, next_path="//evil.com")

    assert callback.headers["location"] == "/productos"


def test_tras_entrar_la_navegacion_muestra_al_duenio(anonymous_client: TestClient) -> None:
    log_in(anonymous_client)

    response = anonymous_client.get("/productos")

    assert response.status_code == 200
    assert "Dueño" in response.text


def test_con_sesion_la_pagina_de_login_lleva_al_catalogo(anonymous_client: TestClient) -> None:
    log_in(anonymous_client)

    response = anonymous_client.get("/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/productos"


def test_la_sesion_guarda_solo_al_duenio_y_ningun_token(anonymous_client: TestClient) -> None:
    log_in(anonymous_client)

    session = read_session(anonymous_client, SECRET_KEY)

    assert set(session) == {"owner"}
    assert set(session["owner"]) == {"email", "name", "login_at"}
    assert session["owner"]["email"] == "dueno@example.com"
    assert TOKEN_SENTINEL not in str(session)


# G1: login sin configurar en local (contracts/configuration.md)


@pytest.fixture
def unconfigured_client() -> Iterator[TestClient]:
    """App local sin GOOGLE_CLIENT_ID. El proveedor explota si se usa: no se contacta a Google."""
    from app.main import create_app  # noqa: PLC0415  (app.main crea la app al importarse)

    settings = Settings(
        _env_file=None,
        environment="local",
        database_url=SecretStr("sqlite://"),
        secret_key=SecretStr(SECRET_KEY),
    )
    assert settings.google_client_id is None
    application = create_app(settings)
    SQLModel.metadata.create_all(application.state.engine)
    application.dependency_overrides[get_identity_provider] = ExplodingIdentityProvider
    with TestClient(application) as client:
        yield client


def test_sin_configurar_google_en_local_el_login_muestra_un_aviso_de_error(
    unconfigured_client: TestClient,
) -> None:
    response = unconfigured_client.get("/login/google", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?aviso=error"
    page = unconfigured_client.get(response.headers["location"])
    assert LOGIN_FAILED_MESSAGE in page.text
    assert "owner" not in read_session(unconfigured_client, SECRET_KEY)


# Historia 2: rechazar a quien no está autorizado (T018, contracts/auth-routes.md)


def _identity_case(provider: FakeIdentityProvider, identity: VerifiedIdentity) -> None:
    provider.identity = identity


@pytest.mark.parametrize(
    ("configure", "notice", "message"),
    [
        (lambda p: _identity_case(p, INTRUDER), "no_autorizado", NOT_AUTHORIZED_MESSAGE),
        (lambda p: _identity_case(p, UNVERIFIED_OWNER), "no_autorizado", NOT_AUTHORIZED_MESSAGE),
        (lambda p: setattr(p, "failure", LoginFailed("cancelado")), "cancelado", CANCELLED_MESSAGE),
        (
            lambda p: setattr(p, "failure", LoginFailed("state_invalido")),
            "cancelado",
            CANCELLED_MESSAGE,
        ),
        (lambda p: setattr(p, "failure", LoginFailed("red")), "error", LOGIN_FAILED_MESSAGE),
        (
            lambda p: setattr(p, "failure", LoginFailed("sin_id_token")),
            "error",
            LOGIN_FAILED_MESSAGE,
        ),
    ],
    ids=[
        "correo_fuera_de_la_lista",
        "correo_no_verificado",
        "cancelado_en_google",
        "state_invalido",
        "fallo_de_red",
        "sin_id_token",
    ],
)
def test_un_login_rechazado_vuelve_al_login_con_su_aviso_y_sin_sesion(
    anonymous_client: TestClient,
    identity_provider: FakeIdentityProvider,
    configure: Callable[[FakeIdentityProvider], None],
    notice: str,
    message: str,
) -> None:
    configure(identity_provider)

    callback = log_in(anonymous_client, next_path="/productos/7")

    assert callback.status_code == 303
    assert callback.headers["location"] == f"/login?aviso={notice}"
    # La sesión queda vacía: ni dueño, ni destino pendiente, ni el estado temporal del login.
    assert read_session(anonymous_client, SECRET_KEY) == {}
    page = anonymous_client.get(callback.headers["location"], follow_redirects=False)
    assert page.status_code == 200
    assert message in page.text


def test_un_login_rechazado_borra_tambien_una_sesion_anterior(
    anonymous_client: TestClient, identity_provider: FakeIdentityProvider
) -> None:
    log_in(anonymous_client)
    identity_provider.identity = INTRUDER

    log_in(anonymous_client)

    assert read_session(anonymous_client, SECRET_KEY) == {}


@pytest.mark.parametrize("notice", ["<script>alert(1)</script>", "desconocido"])
def test_un_aviso_desconocido_no_se_muestra_ni_se_refleja(
    anonymous_client: TestClient, notice: str
) -> None:
    page = anonymous_client.get("/login", params={"aviso": notice})

    assert page.status_code == 200
    assert 'role="alert"' not in page.text
    assert "alert(1)" not in page.text
    assert "desconocido" not in page.text


def test_los_rechazos_no_dejan_correos_ni_tokens_en_logs_ni_respuestas(
    anonymous_client: TestClient,
    identity_provider: FakeIdentityProvider,
    app_log: pytest.LogCaptureFixture,
) -> None:
    identity_provider.identity = INTRUDER

    callback = log_in(anonymous_client)
    page = anonymous_client.get(callback.headers["location"])

    assert "Inicio de sesión rechazado: no_autorizado" in app_log.text
    for text in (app_log.text, callback.text, page.text):
        assert "intruso@gmail.com" not in text
        assert TOKEN_SENTINEL not in text
