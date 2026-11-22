"""Medición manual de modelos de Gemini sobre el banco de mensajes (PED-16, research R2 y R14).

Llama a la API real con la clave de quien lo ejecuta: no es una prueba y la CI no lo corre. Mide
la cadena de la app (agente, instrucciones, `build_lines`) y guarda, sin el texto de los mensajes
ni la clave:

- `mediciones.csv`: una fila por petición;
- `mediciones_lineas.csv`: una fila por línea devuelta, con los ids y la cantidad tal como los dio
  el modelo (un id inventado se ve como inventado) y el estado y el motivo que les puso el código.
  Una respuesta válida sin líneas no deja filas ahí.

Una franja interrumpida se reanuda con el mismo comando: solo se piden los pares mensaje-modelo
que faltan. Lo ya medido no se repite, haya salido bien o mal.

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
DESTINO_LINEAS = DESTINO.with_name("mediciones_lineas.csv")
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

COLUMNAS_LINEAS = (
    "fecha",
    "franja",
    "modelo",
    "mensaje",
    "linea",
    "product_id",
    "variant_id",
    "cantidad",
    "estado",
    "motivo",
)

Fila = dict[str, str]


def decir(texto: str = "") -> None:
    """Escribe en la consola de quien ejecuta el script."""
    print(texto, flush=True)  # noqa: T201  (script manual de consola)


async def medir(
    agente: Agent[None, QuoteExtraction], caso: CasoBanco
) -> tuple[Fila, list[Fila], str]:
    """Hace una petición y devuelve su fila, sus líneas y, si falló, el detalle para la consola."""
    catalogo = CATALOGOS[caso.negocio]
    codigo = detalle = ""
    acierto: Acierto | None = None
    lineas: list[Fila] = []
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
        borradores = build_lines(respuesta.output, catalogo)
        acierto = puntuar(caso.esperado, borradores)
        # Ids y cantidad del modelo, sin `customer_text`; estado y motivo del código.
        lineas = [
            {
                "mensaje": caso.id,
                "linea": str(posicion),
                "product_id": texto_o_vacio(devuelta.product_id),
                "variant_id": texto_o_vacio(devuelta.variant_id),
                "cantidad": texto_o_vacio(devuelta.quantity),
                "estado": borrador.status.value,
                "motivo": texto_o_vacio(borrador.review_reason),
            }
            for posicion, (devuelta, borrador) in enumerate(
                zip(respuesta.output.lines, borradores, strict=True), start=1
            )
        ]
    fila = {
        "mensaje": caso.id,
        "duracion_ms": str(round((time.monotonic() - inicio) * 1000)),
        "resultado": resultado.value,
        "codigo_http": codigo,
        "esperados": str(acierto.esperados) if acierto else "",
        "correctos": str(acierto.correctos) if acierto else "",
        "sobrantes": str(acierto.sobrantes) if acierto else "",
    }
    return fila, lineas, detalle


def texto_o_vacio(valor: object) -> str:
    """El valor como texto, o vacío si no hay."""
    return "" if valor is None else str(valor)


def leer_filas(fecha: str) -> list[Fila]:
    """Filas ya medidas ese día."""
    if not DESTINO.exists():
        return []
    with DESTINO.open(newline="", encoding="utf-8") as archivo:
        return [fila for fila in csv.DictReader(archivo) if fila["fecha"] == fecha]


def guardar(destino: Path, columnas: tuple[str, ...], filas: list[Fila]) -> None:
    """Agrega filas al momento, para no perder lo medido si la corrida se interrumpe."""
    es_nuevo = not destino.exists()
    with destino.open("a", newline="", encoding="utf-8") as archivo:
        salida = csv.DictWriter(archivo, columnas, lineterminator="\n")
        if es_nuevo:
            salida.writeheader()
        salida.writerows(filas)


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
    """Mide o reanuda una franja: cada mensaje una vez por modelo, intercalando los modelos."""
    fecha = datetime.datetime.now(COLOMBIA).date().isoformat()
    hechas = {
        (fila["mensaje"], fila["modelo"]) for fila in leer_filas(fecha) if fila["franja"] == franja
    }
    peticiones = [(caso, modelo) for caso in MENSAJES for modelo in MODELOS]
    pendientes = [
        (numero, caso, modelo)
        for numero, (caso, modelo) in enumerate(peticiones, start=1)
        if (caso.id, modelo) not in hechas
    ]
    if not pendientes:
        raise SystemExit(f"La franja {franja} de {fecha} ya está completa en {DESTINO}")
    if hechas:
        decir(f"Se reanuda la franja {franja}: {len(hechas)} hechas, {len(pendientes)} pendientes")
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
    for orden, (numero, caso, modelo) in enumerate(pendientes):
        if orden > 0:
            await asyncio.sleep(PAUSA_S)
        fila, lineas, detalle = await medir(agentes[modelo], caso)
        if orden == 0 and fila["codigo_http"] in ERRORES_DE_ARRANQUE:
            raise SystemExit(f"Error de clave o configuración, no se guardó nada: {detalle}")
        contexto = {"fecha": fecha, "franja": franja, "modelo": modelo}
        guardar(DESTINO_LINEAS, COLUMNAS_LINEAS, [{**contexto, **linea} for linea in lineas])
        guardar(DESTINO, COLUMNAS, [{**contexto, **fila}])
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
