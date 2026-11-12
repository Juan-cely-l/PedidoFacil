"""Pruebas de .env.example: documenta todas las variables y no trae secretos (FR-016, SC-007)."""

import re
from pathlib import Path

import pytest

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
# Las define la plataforma de despliegue, no quien configura la app.
PLATFORM_VARIABLES = {"RENDER_GIT_COMMIT"}
# Nunca deben tener un valor activo en el ejemplo: o son secretos o dependen del ambiente.
MUST_BE_COMMENTED = ("SECRET_KEY", "GEMINI_API_KEY", "DATABASE_URL", "LOG_LEVEL")


def _settings_variables() -> list[str]:
    """Nombre de la variable de entorno de cada campo de Settings."""
    names = []
    for field_name, field in Settings.model_fields.items():
        alias = field.validation_alias
        names.append(alias if isinstance(alias, str) else field_name.upper())
    return [name for name in names if name not in PLATFORM_VARIABLES]


def _active_lines() -> list[str]:
    """Líneas sin comentar del archivo."""
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


@pytest.mark.parametrize("variable", _settings_variables())
def test_cada_variable_de_la_configuracion_esta_documentada(variable: str) -> None:
    content = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert re.search(rf"^#?\s*{variable}=", content, flags=re.MULTILINE)


def test_el_ejemplo_sirve_para_desarrollo_local() -> None:
    assert "ENVIRONMENT=local" in _active_lines()


@pytest.mark.parametrize("variable", MUST_BE_COMMENTED)
def test_secretos_y_valores_por_ambiente_quedan_comentados(variable: str) -> None:
    assert not any(line.startswith(f"{variable}=") for line in _active_lines())
