# Especificación: PED-93 · HU-20 Bot de Telegram (versión recortada)

**Rama**: `feature/PED-93-bot-telegram` · **Fecha**: 2026-11-24 · **Estado**: borrador para revisión

Como cliente, quiero escribirle al bot de Telegram del negocio y recibir el catálogo o una
cotización con los precios reales, para no esperar a que el dueño esté disponible.

Versión recortada por tiempo: la entrega es el 26 de noviembre y el bot tiene unas 3 horas en
total. **La brevedad es un requisito.**

## Alcance

1. **Webhook** en `app/routers/telegram.py` que recibe las actualizaciones de la Bot API y valida
   el token secreto. Rechaza toda petición sin él (constitución, principio VI).
2. **Catálogo**: un comando le lista al cliente los productos y variantes de `list_quotable_items`.
   La IA no interviene.
3. **Cotización**: cualquier otro texto se cotiza con `quote_message` de HU-08, **sin modificar el
   servicio**. La IA identifica productos y cantidades; el código toma los precios del catálogo y
   calcula subtotales y total.
4. **Producto no reconocido**: el bot no responde con un error. Dice qué no encontró y qué sí hay,
   para que el cliente corrija sin abandonar la conversación. El dueño recibe aviso por Telegram.
5. **Falla o tiempo agotado de la IA**: el bot responde que el dueño revisará el pedido, y le
   notifica.

## Fuera de alcance

No se escribe ni se deja preparado:
- botones «Aceptar» y «Cambiar», y la creación de pedidos;
- código de reclamo para el cliente;
- inventario o existencias;
- registrar el webhook con `setWebhook` desde código: es un paso manual de despliegue, con `curl`;
- límite de mensajes por cliente (ver Riesgos).

## Escenarios de aceptación

**Webhook**
1. Una petición sin la cabecera `X-Telegram-Bot-Api-Secret-Token`, o con un valor distinto,
   responde **401** y no procesa nada.
2. Con el bot sin configurar (falta el token o el secreto), el webhook responde **404**.
3. Una actualización válida responde **200 de inmediato**; la respuesta al cliente se procesa
   después de responder, para que Telegram no reintente mientras la IA piensa.
4. Una actualización sin mensaje de texto (sticker, foto, mensaje editado) no llama a la IA.

**Catálogo**
5. `/catalogo` responde con cada ítem cotizable, su variante y su precio, en el orden de
   `list_quotable_items`. Sin catálogo: «Todavía no hay productos disponibles».
6. `/start` responde un saludo breve que explica qué escribir y menciona `/catalogo`.

**Cotización**
7. Un mensaje con productos reconocidos responde las líneas (etiqueta, cantidad y subtotal) y el
   total, en pesos con separador de miles. Termina con «El dueño te confirmará el pedido».
8. Con alguna línea «Por revisar»:
   - las líneas reconocidas se cotizan igual, y el total solo las incluye;
   - para cada línea pendiente, el bot cita lo que escribió el cliente y dice por qué no la
     cotizó: «no lo encontré», «¿qué presentación?» con las variantes de ese producto, o «la
     cantidad no es válida»;
   - si nada se reconoció, envía el catálogo para que el cliente elija;
   - **el dueño recibe un aviso** con el número de la cotización y su enlace.
9. Un mensaje que no es un pedido (cero líneas, como R09): el bot responde cómo pedir y menciona
   `/catalogo`. Sin aviso al dueño.
10. Si la IA falla, tarda más del tiempo de espera o está desactivada (`ai_outcome` distinto de
    `ok`): «Recibimos tu pedido; el dueño lo revisará y te escribirá». **El dueño recibe un aviso**
    con el número de la cotización y su enlace.
11. Mensaje demasiado largo: el bot pide uno más corto y no llama a la IA.

**Privacidad y robustez**
12. Ningún log contiene el texto del cliente, su nombre ni su chat id (principio VI); solo tipos y
    resultados.
13. Si enviar un mensaje a Telegram falla, se registra el tipo de error y el webhook no se cae.
14. Una respuesta de más de 4096 caracteres, el límite de Telegram, se parte en varios mensajes.

## Requisitos

- **FR-01**: el servicio de cotización de HU-08 no se modifica. El bot lo llama igual que la web,
  con el día de Colombia y `AI_TIMEOUT_SECONDS`.
- **FR-02**: ningún precio sale de la IA ni del mensaje: los montos salen del `Quote` guardado y
  de `list_quotable_items`.
- **FR-03**: los mensajes al cliente no llevan datos de otros clientes ni información interna:
  nada de ids de cotización, nombres de modelos ni detalles de errores.
- **FR-04**: las pruebas simulan la Bot API con `httpx2.MockTransport` y la IA con `FunctionModel`
  o `TestModel`, con `ALLOW_MODEL_REQUESTS=False`. Ninguna prueba llama a un servicio real.
- **FR-05**: sin dependencias nuevas.

## Decisiones para revisar

| # | Decisión | Por qué |
|---|---|---|
| D1 | Cliente HTTP `httpx2.AsyncClient`, según la constitución 1.3.2. | Al redactar esta especificación, la constitución todavía decía `httpx`. Se verificó que `httpx` no está declarado en `pyproject.toml` y llega solo de forma transitiva, por `fastapi[standard]` y `google-genai`, mientras que `httpx2` es dependencia directa y ya lo usa el login de PED-15. La constitución se corrigió en el commit `d8708d9`. |
| D2 | Variables `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` y `OWNER_TELEGRAM_CHAT_ID`, las que ya están en `.env.example`. Son opcionales: sin token o secreto, el bot queda apagado (404). | Un despliegue sin configurar el bot no debe dejar de arrancar. |
| D3 | Ruta `POST /telegram/webhook`, agregada a `PUBLIC_PATHS` y a la prueba de rutas públicas. | Telegram no tiene sesión: la protege el secreto, no el login. Ampliar lo público exige tocar los dos sitios, por diseño. |
| D4 | Responder 200 y procesar con `BackgroundTasks`. | Con la IA, la respuesta puede tardar hasta 10 s. Un error o una demora harían que Telegram reintentara la misma actualización y gastara cuota de Gemini otra vez. |
| D5 | El catálogo muestra los precios. | Son los precios públicos del negocio, y salen de `list_quotable_items`. |
| D6 | Texto plano, sin `parse_mode`. | Evita escapar Markdown o HTML del texto del cliente y no hay riesgo de formato inyectado. |
| D7 | El aviso al dueño lleva el número de la cotización, el enlace `PUBLIC_BASE_URL/cotizaciones/{id}` y el motivo. | El dueño corrige en la web, que ya existe (HU-08). |

## Riesgos

- **Cuota de Gemini**: con el bot, cada mensaje de cualquier cliente consume una petición, y el
  volumen deja de estar bajo el control del dueño. Con N peticiones diarias caben N/2
  cotizaciones (research R2 de PED-16). Sin límite por cliente en esta versión. Mitigan la
  validación previa del servicio (mensajes vacíos o largos no llegan a la IA) y el camino manual.
- **Render Free se suspende**: el primer mensaje tras la inactividad puede tardar unos 50 s, y
  Telegram puede reintentarlo. Se acepta para la demostración.
