"""Reglas puras del acceso del dueño (app/services/auth.py), sin HTTP."""

from typing import Any

import pytest

from app.services.auth import is_authorized, normalize_email, safe_next_path, start_session
from app.services.identity import VerifiedIdentity

# Normalización de correos para la lista blanca (T003)


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("  Dueno@Gmail.COM ", "dueno@gmail.com"),
        ("dueno@example.com", "dueno@example.com"),
        ("", ""),
    ],
)
def test_normalize_email_recorta_y_no_distingue_mayusculas(email: str, expected: str) -> None:
    assert normalize_email(email) == expected


# Destino de retorno tras el login (T007, research.md R4)


@pytest.mark.parametrize(
    "raw",
    ["/productos/7", "/productos?x=1", "/productos", "/productos?inactivos=1"],
)
def test_safe_next_path_acepta_paths_propios(raw: str) -> None:
    assert safe_next_path(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        # Los cinco casos del diseño de seguridad: URL absolutas o que el navegador trata así.
        "https://evil.com",
        "//evil.com",
        r"/\evil.com",
        r"\\evil.com",
        r"https:/\evil.com",
        # Otros destinos que no son paths propios.
        None,
        "",
        "productos",
        "//evil.com/productos",
        r"/productos\x",
        "http:/evil.com",
        "javascript:alert(1)",
        # Las rutas del propio login no son destinos válidos.
        "/login",
        "/login/google",
        "/auth/google/callback",
        "/logout",
        # Caracteres de control.
        "/productos\n",
        "/productos\t",
    ],
)
def test_safe_next_path_rechaza_destinos_externos_o_ambiguos(raw: str | None) -> None:
    assert safe_next_path(raw) is None


# Inicio de sesión: la sesión se limpia antes de escribir al dueño (T008, research.md R5)


def test_start_session_limpia_la_sesion_y_guarda_solo_al_duenio() -> None:
    session: dict[str, Any] = {
        "basura": 1,
        "_state_google_x": {"data": {"nonce": "n", "hint": "TOKEN-CENTINELA-X"}},
        "login_next": "/productos",
    }
    identity = VerifiedIdentity(email=" Dueno@Example.com ", email_verified=True, name="Dueño")

    start_session(session, identity, now=1_795_000_000.0)

    assert session == {
        "owner": {"email": "dueno@example.com", "name": "Dueño", "login_at": 1_795_000_000.0}
    }


# Lista blanca: solo correos verificados que estén en OWNER_EMAILS (T017, research.md R6)

OWNER_EMAILS = frozenset({"dueno@example.com"})


def test_un_correo_verificado_de_la_lista_esta_autorizado_sin_importar_mayusculas() -> None:
    identity = VerifiedIdentity(email="Dueno@Example.com ", email_verified=True, name="Dueño")

    assert is_authorized(identity, OWNER_EMAILS) is True


def test_un_correo_fuera_de_la_lista_no_esta_autorizado() -> None:
    identity = VerifiedIdentity(email="intruso@gmail.com", email_verified=True, name="Intruso")

    assert is_authorized(identity, OWNER_EMAILS) is False


def test_un_correo_no_verificado_no_esta_autorizado_aunque_este_en_la_lista() -> None:
    identity = VerifiedIdentity(email="dueno@example.com", email_verified=False, name="Dueño")

    assert is_authorized(identity, OWNER_EMAILS) is False


def test_con_la_lista_vacia_nadie_esta_autorizado() -> None:
    identity = VerifiedIdentity(email="dueno@example.com", email_verified=True, name="Dueño")

    assert is_authorized(identity, frozenset()) is False
