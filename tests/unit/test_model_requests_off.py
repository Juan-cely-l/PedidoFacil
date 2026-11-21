"""Ninguna prueba puede llamar a un modelo real (constitución II, FR-020, research R10)."""

import pytest
from pydantic_ai import Agent, models
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider


def test_las_pruebas_no_permiten_peticiones_a_modelos_reales() -> None:
    assert models.ALLOW_MODEL_REQUESTS is False


def test_un_modelo_de_gemini_falla_antes_de_tocar_la_red() -> None:
    # Precondición: sin el bloqueo global, esta prueba llamaría de verdad a Google.
    assert models.ALLOW_MODEL_REQUESTS is False, "el bloqueo global no está activo"
    model = GoogleModel("gemini-3.5-flash-lite", provider=GoogleProvider(api_key="clave-falsa"))
    agent = Agent(model)

    with pytest.raises(RuntimeError, match="ALLOW_MODEL_REQUESTS"):
        agent.run_sync("hola")
