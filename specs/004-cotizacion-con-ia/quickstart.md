# Validación rápida: PED-16 · HU-08 Cotización con IA

Guía para comprobar la historia de punta a punta. Las rutas están en
[contracts/quote-pages.md](contracts/quote-pages.md) y los datos en [data-model.md](data-model.md).

## Pruebas automáticas (sin red)

```bash
uv run pytest            # incluye tests/unit/test_quote_*.py y tests/integration/test_quote_*.py
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Qué tiene que pasar:
- **Las pruebas sin red**: ninguna llama a Gemini. `ALLOW_MODEL_REQUESTS=False` está activo y una
  prueba lo verifica.
- **Frontera del servicio**: la prueba confirma que `app.services.quotes` no carga
  FastAPI, Starlette ni Jinja2.
- **Salida de la IA**: la prueba confirma que la salida no tiene campos de precio.
- **Centinela**: `MENSAJE-CENTINELA` no aparece en la salida de `uv run pytest -s`.

## Recorrido local sin IA (`AI_PROVIDER=fake`, el valor por defecto)

1. `uv run alembic upgrade head`: crea `quote` y `quote_line`.
2. `uv run fastapi dev app/main.py`, con la sesión iniciada (PED-15) y al menos un producto con
   variantes en el catálogo.
3. «Cotizaciones» → «Nueva cotización». Pega «2 tortas de chocolate medianas para el sábado» y
   pulsa «Cotizar».
   - **Resultado**: un borrador con el mensaje y el aviso «La IA está desactivada en este
     ambiente…».
4. Agrega una línea eligiendo «Torta de chocolate — Tamaño: Mediana» con cantidad 2.
   - **Resultado**: el subtotal es el precio × 2 y el total coincide.
5. Cambia la cantidad a 3, elimina la línea y completa la entrega.
   - **Resultado**: el total se recalcula cada vez y no hay ningún campo de precio editable.
6. Vuelve a «Cotizaciones».
   - **Resultado**: el borrador aparece primero, con su total.

## Recorrido local con Gemini

1. En `.env`, define `AI_PROVIDER=gemini` y `GEMINI_API_KEY=<clave>`. Opcionalmente, ajusta
   `GEMINI_MODEL`.
2. Repite el paso 3 del recorrido anterior.
   - **Resultado esperado**: en 10 s o menos, la línea «Torta de chocolate — Tamaño: Mediana» con
     cantidad 2 y la fecha del próximo sábado. O, si la IA tarda o falla, el borrador manual con su
     aviso, nunca una página de error.
3. Cotiza «una docena de empanadas», que no está en el catálogo.
   - **Resultado**: una línea «Por revisar» sin precio, fuera del total.
4. Cotiza «una torta de chocolate», que tiene variantes.
   - **Resultado**: «Por revisar», con el motivo «falta la presentación».
5. Revisa la consola.
   - **Resultado**: una línea por cotización con el resultado y la duración, sin el texto del
     mensaje.

## Medición de modelos (antes del merge)

No bloquea el desarrollo: se corre en paralelo, en cuanto existen el banco y el agente.

```bash
uv run --no-sync python -m scripts.medir_gemini --franja manana   # y luego --franja tarde
```

Sigue el protocolo de [research.md R2](research.md#cómo-se-vuelve-a-medir-antes-del-merge-y-cada-vez-que-se-dude):
- **Muestra**: los 12 o más mensajes del banco (R14) con los 3 modelos, en dos franjas del mismo
  día (102 peticiones con los 17 mensajes actuales).
- **Reporte**: por modelo, el porcentaje de respuestas válidas en 10 s o menos, p50, p95 y el
  porcentaje de acierto. El acierto del modelo elegido valida SC-008 (≥ 80 %).
- **Resultado**: se guarda en `specs/004-cotizacion-con-ia/mediciones.csv`.
- **Elección**: el modelo elegido se registra en research.md R2 y, si cambia, en `GEMINI_MODEL` en
  Render.

## Producción (después del merge)

1. **Antes del merge**, en Render: `AI_PROVIDER=gemini`, más `GEMINI_API_KEY` y, si la medición
   lo indicó, `GEMINI_MODEL` y `GEMINI_FALLBACK_MODEL`.
2. **Después del despliegue**: `/health` reporta el commit nuevo. El Start Command aplica la
   migración.
3. Con la sesión iniciada, cotiza un mensaje real.
   - **Resultado**: el borrador aparece en menos de 15 s, o el borrador manual con su aviso.
