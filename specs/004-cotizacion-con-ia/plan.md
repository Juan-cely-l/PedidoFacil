# Plan de implementación: PED-16 · HU-08 Cotización con IA

**Rama**: `feature/PED-16-cotizacion-con-ia` | **Fecha**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Entrada**: especificación de `specs/004-cotizacion-con-ia/spec.md`, más las decisiones
pendientes que pidió el autor el 2026-11-20: el modelo de Gemini, el tiempo de espera, la forma de
las instrucciones y la justificación de pydantic-ai.

## Resumen

El dueño pega el mensaje del cliente. Un agente de pydantic-ai con Gemini devuelve una
`QuoteExtraction` tipada **sin campos de precio**, y el código arma un borrador con los precios de
`list_quotable_items`. Enfoque:

- **La IA interpreta y el código calcula**:
  - la IA devuelve los ids del catálogo que vio en las instrucciones, cantidades, expresiones de
    fecha, hora, modalidad y dirección;
  - el código valida cada id contra lo cotizable (no válido → «Por revisar»), copia el precio y la
    etiqueta en la línea, calcula subtotales y total en enteros y convierte las fechas relativas
    con la hora de Colombia (R5, R7, R9).
- **Modelo**: `gemini-3.5-flash-lite` con el razonamiento apagado, y respaldo `gemini-3.8-flash`
  solo ante errores rápidos (503 o 429). Es una elección **provisional**: la confirma o cambia un
  protocolo de medición repetible antes del merge, y los nombres se cambian por variable de
  entorno (R2).
- **Banco de mensajes**: al menos 12 mensajes escritos como por WhatsApp, cada uno con su
  resultado esperado. Es la entrada de las pruebas de extracción (con `FunctionModel`) y del
  script de medición, que con el modelo real reporta latencia y acierto: decide el modelo y
  valida SC-008 (≥ 80 % de productos y cantidades correctos) en una sola pasada (R2, R14).
- **Tiempo de espera de 10 s**, como un único reloj sobre toda la consulta, con el respaldo y el
  reintento incluidos. La configuración rechaza valores mayores de 15 s (principio V).
- **Camino manual**: cualquier falla del proveedor (tiempo agotado, error o salida inválida) deja
  un borrador sin líneas con el mensaje y un aviso. Nunca una página de error (R4).
- **Instrucciones**: reglas fijas en `instructions`, más un mensaje con dos bloques delimitados,
  `<catalogo>` (ids y nombres, **sin precios**) y `<mensaje_cliente>`, tratado como datos (R6).
  La defensa contra la inyección de instrucciones no es el prompt, sino la estructura: ids
  validados contra el catálogo y un esquema sin precios. Importa ya, porque con HU-20 los clientes
  escribirán directo al modelo a través de este mismo servicio.
- **Frontera reutilizable**: `app/services/quotes.py` y `app/services/quote_ai.py` no importan
  FastAPI, Starlette, Jinja2 ni `app.config`. Una prueba lo verifica en un intérprete limpio, para
  que HU-20 llame al mismo servicio (R8).
- **Dependencia nueva**: `pydantic-ai-slim[google]` (R1).

Decisiones en [research.md](research.md).

## Contexto técnico

**Lenguaje/versión**: Python 3.12 (uv)

**Dependencias principales**:
- existentes: FastAPI, SQLModel, Alembic y Jinja2;
- **nueva**: `pydantic-ai-slim[google]>=2.71`, que trae `google-genai` (R1);
- sin dependencias nuevas de desarrollo: `time-machine` ya está.

**Almacenamiento**: tablas nuevas `quote` y `quote_line`, con una migración de Alembic
([data-model.md](data-model.md)). No se guardan totales: se calculan al leer.

**Pruebas**:
- `tests/unit`:
  - el banco de mensajes: invariantes, conversión de cada mensaje con un `FunctionModel` y
    puntuación (R14);
  - conversión de la extracción en líneas, con un `FunctionModel` por caso;
  - inyección de instrucciones: un id inexistente y un campo `price` no pasan;
  - fallas: lentitud, 503, salida con precio o con un tipo inválido;
  - el respaldo con dos `FunctionModel`;
  - fechas con `time-machine`;
  - instrucciones sin precios;
  - salida sin campos de precio;
  - la frontera del servicio, en un intérprete limpio;
  - la configuración;
  - el centinela en los logs.
- `tests/integration`: páginas con `TestClient`, sesión iniciada y extractor sustituido.
- `ALLOW_MODEL_REQUESTS=False` global en `conftest.py` (R10).

**Plataforma**: Render. El Start Command ya aplica las migraciones; se agregan variables en
Environment.

**Tipo de proyecto**: servicio web (monolito FastAPI en capas)

**Metas de rendimiento**:
- la consulta a la IA dura como máximo `AI_TIMEOUT_SECONDS` (10 s);
- el borrador queda visible en menos de 15 s de principio a fin (SC-001);
- el resto de la petición son dos o tres consultas a la base.

**Restricciones**:
- la IA nunca fija precios;
- sin texto del mensaje en los logs;
- sin red en las pruebas;
- `mypy --strict`;
- cobertura ≥ 80 % con ramas;
- la página es usable a 360 px.

**Escala/alcance**: 1 dueño, catálogo de decenas de productos. El trabajo es de unos 6 archivos de
código, 3 plantillas, 1 migración, 1 script de medición y unos 8 archivos de prueba.

## Verificación de la constitución (1.3.0)

*Puerta: antes de la Fase 0 y de nuevo tras la Fase 1.*

| Principio | Cumplimiento | Estado |
|---|---|---|
| I. TDD | Cada tarea irá precedida de su prueba; commits `test` → `feat` → `refactor` | ✅ |
| II. Pruebas deterministas | `ALLOW_MODEL_REQUESTS=False` global y verificado; `FunctionModel` para éxito, lentitud, error, salida inválida y respaldo; fechas con `time-machine`; SQLite en memoria; el script de medición está fuera de `tests/` y de la CI (R2, R10) | ✅ |
| III. Calidad | Sin cambios en la configuración de las herramientas | ✅ |
| IV. Stack y YAGNI | Pydantic AI con Gemini, según el stack; `pydantic-ai-slim[google]` justificada (R1); montos enteros; capas router → servicio → repositorio; sin interfaz propia para la IA (se usa `Agent.override`); sin HTMX (R13). La configuración del modelo y del tiempo de espera es por variable de entorno, por el uso real de volver a medir (R2) | ✅ |
| V. La IA asiste | Sin campos de precio en la salida (`extra="forbid"`, verificado); acierto ≥ 80 % medido con el banco y el modelo real (SC-008, R2); precios solo de `list_quotable_items`; ids inválidos → «Por revisar»; nada se inventa; respaldo manual ante fallas, lentitud de más de 15 s (10 s configurado, tope validado) y datos inválidos; el dueño corrige todo antes de enviar | ✅ |
| VI. Seguridad y privacidad | El mensaje y la dirección no van a los logs (centinela); las excepciones del proveedor se registran solo por tipo; la clave está en una variable de entorno; las rutas están protegidas por `require_owner` | ✅ |
| VII. Trazabilidad | Rama `feature/PED-16-…`; commits `tipo(PED-16): …` | ✅ |

**Tras el diseño (Fase 1)**: sin cambios; ninguna violación.

## Estructura del proyecto

### Documentación (esta funcionalidad)

```text
specs/004-cotizacion-con-ia/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── quote-pages.md
│   ├── quote-service.md
│   └── configuration.md
├── checklists/requirements.md
├── mediciones.csv       # lo produce el script de medición (R2)
└── tasks.md             # /speckit-tasks
```

### Código fuente

```text
app/
├── config.py               # MODIFICAR: gemini_model, gemini_fallback_model, ai_timeout_seconds (0 < t ≤ 15)
├── main.py                 # MODIFICAR: construir el agente desde Settings → app.state.quote_extractor;
│                           #   log de arranque con modelos y tiempo de espera; router de cotizaciones
├── models/
│   └── quote.py            # NUEVO: Quote, QuoteLine (tablas), estados y motivos, QuoteRequestInput,
│                           #   LineInput, DeliveryInput
├── repositories/
│   └── quotes.py           # NUEVO: guardar, obtener con líneas, listar
├── services/
│   ├── quote_ai.py         # NUEVO: QuoteExtraction, ExtractedLine, DateExpression (sin precios),
│   │                       #   INSTRUCTIONS, render_catalog_prompt, build_quote_agent, resolve_delivery_date
│   └── quotes.py           # NUEVO: build_lines (pura), quote_message (async), edición, totales; get_quote_extractor
│                           #   vive en el router, no aquí (RD-1)
├── routers/
│   └── quotes.py           # NUEVO: rutas de contracts/quote-pages.md; dependencia get_quote_extractor
└── templates/
    ├── base.html           # MODIFICAR: enlace «Cotizaciones»
    └── quotes/
        ├── list.html       # NUEVO
        ├── new.html        # NUEVO
        └── detail.html     # NUEVO

migrations/versions/
└── 20261121_xxxx_crear_tablas_de_cotizaciones.py   # NUEVO

scripts/
└── medir_gemini.py         # NUEVO: protocolo de R2 sobre el banco: latencia y acierto por modelo
                            #   (manual, llama a la API real; fuera de la CI)

tests/
├── conftest.py             # MODIFICAR: ALLOW_MODEL_REQUESTS=False; fixture del extractor sustituido
├── doubles.py              # MODIFICAR: constructores de FunctionModel (respuesta, lento, 503, inválido)
├── banco_mensajes.py       # NUEVO: CATALOGO, MENSAJES (≥ 12, con lo esperado) y puntuar (R14)
├── unit/
│   ├── test_quote_bank.py         # NUEVO: invariantes del banco, conversión al 100 %, puntuación
│   ├── test_quote_ai.py           # NUEVO: esquema sin precios, instrucciones sin precios, fechas
│   ├── test_quote_service.py      # NUEVO: líneas, totales, fallas → borrador manual, respaldo, edición
│   ├── test_service_boundary.py   # NUEVO: sin fastapi, starlette ni jinja2 en sys.modules (R8)
│   ├── test_model_requests_off.py # NUEVO: un modelo real lanza RuntimeError
│   └── test_config.py             # AMPLIAR: variables nuevas y tope de 15 s
└── integration/
    ├── test_quote_pages.py        # NUEVO: nueva → detalle, lista, edición, validaciones, sin campo de precio
    └── test_quote_logs.py         # NUEVO: centinela fuera de los logs, con éxito y con falla

.env.example                # MODIFICAR: GEMINI_MODEL, GEMINI_FALLBACK_MODEL, AI_TIMEOUT_SECONDS
docs/despliegue.md          # MODIFICAR: AI_PROVIDER=gemini, variables nuevas, cómo volver a medir
```

**Decisiones de estructura**:
- La salida de la IA (`QuoteExtraction`) vive en `services/quote_ai.py` y no en `models/`: no es
  una entidad persistida, sino el contrato con el proveedor.
- `get_quote_extractor` lee `request.app.state` y por eso vive en el router, no en el servicio.
- El servicio recibe `today` y `now` como parámetros: así las pruebas no dependen del reloj, y
  HU-20 los pasa igual.

## Orden de trabajo

**La implementación no depende de la medición.** Todo el desarrollo usa `FunctionModel` y no
toca la API real; la medición solo decide el valor de `GEMINI_MODEL` (y de
`GEMINI_FALLBACK_MODEL`), que son variables de entorno. Los dos trabajos corren en paralelo:

- **Desarrollo**: banco de mensajes → pruebas en rojo → implementación, historia por historia.
- **Medición**: en cuanto existen el banco, el agente y `build_lines`, se corre el script en dos
  franjas de un mismo día. Su resultado se registra en R2 y, si cambia el modelo, en Render, sin
  tocar código.

Lo único que la medición puede bloquear es el merge: si el acierto del modelo elegido queda por
debajo del 80 % (SC-008), se avisa al autor antes de fusionar.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El proveedor sigue congestionado y casi todo cae al camino manual | El camino manual es el diseño, no un error. La medición de R2 dice cuánto pasa; el dueño cotiza a mano en menos de 60 s con el catálogo en un `<select>`. |
| Importar `pydantic_ai` arrastra Starlette u otra pieza web y rompe RD-1 | Verificado el 2026-11-20 con 2.71.0 en Python 3.12: importar `Agent`, `GoogleModel`, `FallbackModel` y `FunctionModel` no carga `fastapi`, `starlette` ni `jinja2`. La prueba de frontera lo vigila si cambia la versión. |
| `google-genai` o alguna de sus dependencias no tiene wheel y la CI con `--no-build` falla | Se comprueba con `uv sync --locked --no-build` al agregar la dependencia; si falla, se detiene y se avisa. |
| El modelo elegido no llega al 80 % de acierto con el banco (SC-008) | Se registra en R2 y se avisa antes del merge; no se ajustan la regla ni el banco para que pase. El dueño corrige las líneas en el borrador, que es el diseño. |
| El esquema de salida es demasiado grande para el modelo liviano | `extra="forbid"`, máximo 30 líneas y un reintento de validación dentro del mismo reloj; si no basta, la medición lo muestra como `invalid_output`. |

## Seguimiento de complejidad

Sin violaciones de la constitución que justificar.
