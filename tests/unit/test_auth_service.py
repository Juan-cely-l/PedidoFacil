"""Reglas puras del acceso del dueño (app/services/auth.py), sin HTTP."""

import pytest

from app.services.auth import normalize_email

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
