"""Medición manual de modelos de Gemini sobre el banco de mensajes (PED-16, research R2 y R14).

Llama a la API real con la clave de quien lo ejecuta: no es una prueba y la CI no lo corre. Mide
la cadena de la app (agente, instrucciones, `build_lines`) y guarda una fila por petición, sin el
texto de los mensajes ni la clave.

    uv run --no-sync python -m scripts.medir_gemini --franja manana
    uv run --no-sync python -m scripts.medir_gemini --franja tarde
"""

import argparse
import asyncio
import csv
import datetime
import math
import os
import time
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_ai import Agent
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelHTTPError,
    ModelTimeoutError,
    UnexpectedModelBehavior,
)

from app.models.quote import AiOutcome
from app.services.quote_ai import QuoteExtraction, build_quote_agent, render_catalog_prompt
from app.services.quotes import build_lines
from tests.banco_mensajes import CATALOGOS, MENSAJES, Acierto, CasoBanco, puntuar

MODELOS = ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash")
ESPERA_MAXIMA_S = 30
PAUSA_S = 5
LIMITE_APP_MS = 10_000
CUOTA_AGOTADA = "429"
# En la primera petición, estos códigos son de clave o de configuración, no del modelo.
ERRORES_DE_ARRANQUE = frozenset({"400", "401", "403"})
COLOMBIA = ZoneInfo("America/Bogota")
DESTINO = Path(__file__).parents[1] / "specs" / "004-cotizacion-con-ia" / "mediciones.csv"
COLUMNAS = (
    "fecha",
    "franja",
    "modelo",
    "mensaje",
    "duracion_ms",
    "resultado",
    "codigo_http",
    "esperados",
    "correctos",
    "sobrantes",
)

Fila = dict[str, str]


def decir(texto: str = "") -> None:
    """Escribe en la consola de quien ejecuta el script."""
    print(texto, flush=True)  # noqa: T201  (script manual de consola)


async def medir(agente: Agent[None, QuoteExtraction], caso: CasoBanco) -> tuple[Fila, str]:
    """Hace una petición y devuelve su fila y, si falló, el detalle para la consola."""
    catalogo = CATALOGOS[caso.negocio]
    codigo = detalle = ""
    acierto: Acierto | None = None
    inicio = time.monotonic()
    try:
        async with asyncio.timeout(ESPERA_MAXIMA_S):
            respuesta = await agente.run(render_catalog_prompt(catalogo, caso.texto))
    except (TimeoutError, ModelTimeoutError):
        resultado = AiOutcome.TIMEOUT
    except UnexpectedModelBehavior as error:
        resultado, detalle = AiOutcome.INVALID_OUTPUT, type(error).__name__
    except ModelHTTPError as error:
        resultado, detalle = AiOutcome.PROVIDER_ERROR, str(error)
        codigo = str(error.status_code)
    except AgentRunError as error:
        resultado, detalle = AiOutcome.PROVIDER_ERROR, type(error).__name__
    else:
        resultado = AiOutcome.OK
        acierto = puntuar(caso.esperado, build_lines(respuesta.output, catalogo))
    fila = {
        "mensaje": caso.id,
        "duracion_ms": str(round((time.monotonic() - inicio) * 1000)),
        "resultado": resultado.value,
        "codigo_http": codigo,
        "esperados": str(acierto.esperados) if acierto else "",
        "correctos": str(acierto.correctos) if acierto else "",
        "sobrantes": str(acierto.sobrantes) if acierto else "",
    }
    return fila, detalle


def leer_filas(fecha: str) -> list[Fila]:
    """Filas ya medidas ese día."""
    if not DESTINO.exists():
        return []
    with DESTINO.open(newline="", encoding="utf-8") as archivo:
        return [fila for fila in csv.DictReader(archivo) if fila["fecha"] == fecha]


def guardar(fila: Fila) -> None:
    """Agrega una fila al momento, para no perder lo medido si la corrida se interrumpe."""
    es_nuevo = not DESTINO.exists()
    with DESTINO.open("a", newline="", encoding="utf-8") as archivo:
        salida = csv.DictWriter(archivo, COLUMNAS, lineterminator="\n")
        if es_nuevo:
            salida.writeheader()
        salida.writerow(fila)


def percentil(valores: list[int], porcentaje: int) -> str:
    """Percentil por rango más cercano."""
    if not valores:
        return "sin datos"
    return f"{sorted(valores)[math.ceil(porcentaje * len(valores) / 100) - 1]} ms"


def resumir(filas: list[Fila]) -> None:
    """Resumen por modelo de todo lo medido en el día (las franjas que ya existan)."""
    decir(f"\nResumen del día. Franjas: {', '.join(sorted({fila['franja'] for fila in filas}))}")
    for modelo in MODELOS:
        propias = [fila for fila in filas if fila["modelo"] == modelo]
        if not propias:
            continue
        validas = [fila for fila in propias if fila["resultado"] == AiOutcome.OK]
        duraciones = [int(fila["duracion_ms"]) for fila in validas]
        a_tiempo = sum(1 for duracion in duraciones if duracion <= LIMITE_APP_MS)
        total = Acierto(
            esperados=sum(int(fila["esperados"]) for fila in validas),
            correctos=sum(int(fila["correctos"]) for fila in validas),
            sobrantes=sum(int(fila["sobrantes"]) for fila in validas),
        )
        sin_cuota = sum(1 for fila in propias if fila["codigo_http"] == CUOTA_AGOTADA)
        decir(f"\n{modelo}: {len(validas)} válidas de {len(propias)}")
        decir(f"  válidas en 10 s o menos: {a_tiempo / len(propias):.1%}")
        decir(f"  p50: {percentil(duraciones, 50)} | p95: {percentil(duraciones, 95)}")
        decir(f"  acierto global: {f'{total.valor:.1%}' if validas else 'sin datos'}")
        if sin_cuota:
            decir(f"  OJO: {sin_cuota} errores 429; son de cuota, no de latencia")
    origenes = Counter(caso.origen for caso in MENSAJES)
    procedencia = ", ".join(f"{origen}: {total}" for origen, total in sorted(origenes.items()))
    decir(f"\nProcedencia del banco ({procedencia}). Ningún mensaje es real (research R14).")


async def correr(franja: str, clave: str) -> None:
    """Mide una franja: cada mensaje una vez por modelo, intercalando los modelos."""
    fecha = datetime.datetime.now(COLOMBIA).date().isoformat()
    if any(fila["franja"] == franja for fila in leer_filas(fecha)):
        raise SystemExit(f"La franja {franja} de {fecha} ya tiene filas en {DESTINO}")
    agentes: dict[str, Agent[None, QuoteExtraction]] = {}
    for modelo in MODELOS:
        agente = build_quote_agent(
            provider="gemini",
            api_key=clave,
            model_name=modelo,
            fallback_model_name=None,
            timeout_seconds=ESPERA_MAXIMA_S,
        )
        if agente is None:
            raise SystemExit(f"No se pudo construir el agente de {modelo}")
        agentes[modelo] = agente
    # Intercalados, cada modelo recibe como mucho una petición cada 15 s (4 por minuto).
    peticiones = [(caso, modelo) for caso in MENSAJES for modelo in MODELOS]
    for numero, (caso, modelo) in enumerate(peticiones, start=1):
        if numero > 1:
            await asyncio.sleep(PAUSA_S)
        fila, detalle = await medir(agentes[modelo], caso)
        if numero == 1 and fila["codigo_http"] in ERRORES_DE_ARRANQUE:
            raise SystemExit(f"Error de clave o configuración, no se guardó nada: {detalle}")
        guardar({"fecha": fecha, "franja": franja, "modelo": modelo, **fila})
        decir(
            f"{numero}/{len(peticiones)} {modelo} {caso.id}: {fila['resultado']} "
            f"{fila['duracion_ms']} ms {detalle[:200]}".rstrip()
        )
    resumir(leer_filas(fecha))


def main() -> None:
    """Punto de entrada del script."""
    opciones = argparse.ArgumentParser(description="Mide los modelos de Gemini con el banco.")
    opciones.add_argument("--franja", required=True, choices=("manana", "tarde"))
    franja: str = opciones.parse_args().franja
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise SystemExit("GEMINI_API_KEY: falta en el entorno")
    asyncio.run(correr(franja, clave))


if __name__ == "__main__":
    main()
