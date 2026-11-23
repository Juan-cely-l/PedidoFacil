"""Construcción del agente de cotización (contracts/quote-service.md, research R2, R3 y R12).

Construir el agente no abre conexiones; cuando una prueba lo ejecuta, su modelo se sustituye con
un `FunctionModel` y el bloqueo global impide cualquier petición real.
"""

import asyncio

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel

from app.services.quote_ai import INSTRUCTIONS, QuoteExtraction, build_quote_agent
from tests.doubles import EMPTY_EXTRACTION, extraction_model

PRIMARY = "gemini-3.5-flash-lite"
FALLBACK = "gemini-3.8-flash"


def _gemini_agent(
    fallback: str | None = FALLBACK, timeout: float = 7.0
) -> Agent[None, QuoteExtraction]:
    agent = build_quote_agent(
        provider="gemini",
        api_key="clave-falsa",
        model_name=PRIMARY,
        fallback_model_name=fallback,
        timeout_seconds=timeout,
    )
    assert agent is not None
    return agent


def test_con_la_ia_desactivada_no_hay_agente() -> None:
    agent = build_quote_agent(
        provider="fake",
        api_key=None,
        model_name=PRIMARY,
        fallback_model_name=FALLBACK,
        timeout_seconds=10,
    )

    assert agent is None


def test_con_gemini_y_sin_clave_no_se_construye_el_agente() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_quote_agent(
            provider="gemini",
            api_key=None,
            model_name=PRIMARY,
            fallback_model_name=None,
            timeout_seconds=10,
        )


def test_con_respaldo_el_modelo_es_un_fallback_de_dos_modelos_de_gemini() -> None:
    model = _gemini_agent().model

    assert isinstance(model, FallbackModel)
    assert all(isinstance(inner, GoogleModel) for inner in model.models)
    assert [inner.model_name for inner in model.models] == [PRIMARY, FALLBACK]


def test_sin_respaldo_el_modelo_es_solo_el_principal() -> None:
    model = _gemini_agent(fallback=None).model

    assert isinstance(model, GoogleModel)
    assert model.model_name == PRIMARY


def test_los_ajustes_del_modelo_siguen_la_investigacion() -> None:
    settings = _gemini_agent(timeout=7.0).model_settings

    # Ajustes fijos, no una función que los calcule en cada ejecución.
    assert isinstance(settings, dict)
    assert settings.get("thinking") is False  # extracción, no razonamiento (R2)
    assert settings.get("timeout") == 7.0
    assert settings.get("request_timeout") == 7.0  # una petición colgada se cancela (R3)
    assert settings.get("max_retries") == 0  # decide el FallbackModel, no el cliente (R3)


def test_la_salida_del_agente_es_la_extraccion_sin_precios() -> None:
    assert _gemini_agent().output_type is QuoteExtraction


def test_el_agente_envia_las_instrucciones_fijas() -> None:
    agent = _gemini_agent()
    model = extraction_model(EMPTY_EXTRACTION)

    with agent.override(model=model):
        result = asyncio.run(agent.run("hola"))

    assert isinstance(result.output, QuoteExtraction)
    assert model.requests[0].instructions == INSTRUCTIONS
