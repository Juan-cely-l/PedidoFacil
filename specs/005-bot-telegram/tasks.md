# Tareas: PED-93 · HU-20 Bot de Telegram (versión recortada)

TDD estricto: cada fase con su rojo, un **⛔ ALTO** para revisar la prueba, el commit `test`,
luego el verde y su commit `feat`. Presupuesto: 70 min hoy y 2 h mañana.

Convenciones de las pruebas: la Bot API con `httpx2.MockTransport`, que registra cada
`sendMessage`; la IA con `FunctionModel` (`tests/doubles.py`); el catálogo con
`seed_reference_catalog`.

## Fase 1: Configuración y webhook seguro (≈ 35 min)

- [x] T001 [P] Pruebas en `tests/unit/test_config.py`: `telegram_bot_token`,
  `telegram_webhook_secret` (ambos `SecretStr | None`) y `owner_telegram_chat_id` (`int | None`)
  se leen de `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` y `OWNER_TELEGRAM_CHAT_ID`; vacíos
  cuentan como ausentes; producción arranca sin ellos; `telegram_enabled` es verdadero solo con
  token y secreto.
- [x] T002 [P] Pruebas en `tests/integration/test_telegram_webhook.py`:
  - sin la cabecera del secreto, o con otra, responde 401 y no llama a la Bot API;
  - con el bot sin configurar, responde 404;
  - con el secreto correcto y una actualización sin texto, responde 200 sin llamar a la IA;
  - la prueba de protección de rutas incluye `/telegram/webhook` entre las públicas.
- [x] T003 Esqueletos con `raise NotImplementedError`: el router y el cliente de la Bot API
  (`app/services/telegram.py`, `send_message(chat_id, text)` sobre `httpx2.AsyncClient`, inyectable).

**⛔ ALTO — revisión de la fase roja 1.** Commit `test(PED-93): pruebas del webhook seguro`.

- [x] T004 Verde: los campos en `app/config.py` y `.env.example` (comentarios); el router en
  `app/routers/telegram.py` con `hmac.compare_digest`, `BackgroundTasks` y la dependencia del
  cliente; `PUBLIC_PATHS`. Commit `feat(PED-93): webhook de Telegram con token secreto`.

## Fase 2: Catálogo (≈ 25 min)

- [x] T005 [P] Pruebas en `tests/unit/test_telegram_replies.py`: formatear el catálogo (etiqueta y
  precio de cada ítem, en orden; mensaje de catálogo vacío); partir en mensajes de como máximo 4096
  caracteres sin cortar una línea. En `tests/integration/test_telegram_webhook.py`: `/catalogo` y
  `/start` responden al chat que escribió, sin llamar a la IA.

**⛔ ALTO — revisión de la fase roja 2.** Commit `test(PED-93): pruebas del catálogo por Telegram`.

- [x] T006 Verde: `app/services/telegram_replies.py` (funciones puras de texto) y el despacho de
  comandos en el router. Commit `feat(PED-93): listar el catálogo por Telegram`.

## Fase 3: Cotización, no reconocidos y fallas de la IA (≈ 75 min)

- [x] T007 [P] Pruebas en `tests/unit/test_telegram_replies.py` para el texto de la cotización a
  partir de un `Quote` guardado:
  - líneas listas con subtotal y total, sin las «Por revisar»;
  - cada motivo con su frase y el texto del cliente;
  - «¿qué presentación?» con las variantes de ese producto;
  - el catálogo cuando nada se reconoció;
  - cero líneas: cómo pedir;
  - `ai_outcome` distinto de `ok`: «el dueño lo revisará»;
  - sin ids, nombres de modelos ni detalles de errores.
- [x] T008 [P] Pruebas en `tests/integration/test_telegram_webhook.py`, de punta a punta:
  - un mensaje con dos productos responde la cotización con los precios del catálogo y no avisa
    al dueño;
  - uno con un producto inexistente responde qué no encontró y el catálogo, y avisa al dueño con
    el enlace;
  - la IA lenta (`slow_model`) o con 503 (`failing_model`) responde «el dueño lo revisará» y
    avisa al dueño;
  - un mensaje de más de 2000 caracteres no llama a la IA;
  - si `sendMessage` falla, se registra solo el tipo y responde 200;
  - ningún log contiene el texto, el nombre ni el chat id del cliente.
- [x] T009 Esqueletos de `quote_reply` y `owner_notice` en `app/services/telegram_replies.py`.

**⛔ ALTO — revisión de la fase roja 3.** Commit `test(PED-93): pruebas de cotizar por Telegram`.

- [x] T010 Verde: los textos, y en el router la llamada a `quote_message` (día de Colombia,
  `AI_TIMEOUT_SECONDS`) y los avisos al dueño. Commit `feat(PED-93): cotizar por Telegram`.

## Fase 4: Cierre (≈ 15 min)

- [x] T011 `docs/despliegue.md`: las tres variables en Render y el `curl` a `setWebhook` con
  `secret_token`. `uv run pytest`, `ruff`, `mypy` y `pre-commit run --all-files`. Commit
  `docs(PED-93): desplegar el bot de Telegram`.
