# Contrato: páginas de cotización

Todas las rutas exigen la sesión del dueño, por la dependencia global `require_owner` de PED-15.
Ninguna se agrega a `PUBLIC_PATHS`, y la prueba de cobertura de rutas las recorre sola. Se usan
formularios HTML con Post/Redirect/Get: si todo sale bien, la respuesta es `303` al detalle; si
hay errores, se vuelve a mostrar la página con lo escrito y un mensaje en español junto al campo.

| Método y ruta | Qué hace | Respuestas |
|---|---|---|
| `GET /cotizaciones` | Lista de cotizaciones de la más reciente a la más antigua, con fecha de creación, estado, total, pendientes («2 por revisar») y enlace al detalle (FR-016). Sin cotizaciones: «Aún no hay cotizaciones» y un enlace a «Nueva cotización». | 200 |
| `GET /cotizaciones/nueva` | Formulario con un `<textarea name="message">` (máx. 2000) y el botón «Cotizar». Si no hay nada cotizable, en lugar del formulario aparece «Primero crea productos en el catálogo» con un enlace a `/productos/nuevo`. | 200 |
| `POST /cotizaciones` | Cotiza el mensaje (`quote_message`) y guarda el borrador, con o sin IA. | 303 → `/cotizaciones/{id}`; 422 si el mensaje está vacío o es demasiado largo (no llama a la IA); 409 si no hay nada cotizable (no llama a la IA) |
| `GET /cotizaciones/{id}` | Detalle (ver abajo). | 200; 404 si no existe |
| `POST /cotizaciones/{id}/lineas` | Agrega una línea: `item` y `quantity`. | 303 → detalle; 422 si hay errores; 404 |
| `POST /cotizaciones/{id}/lineas/{line_id}` | Cambia `item` y/o `quantity` de una línea; con `item` válido, resuelve una línea «Por revisar». | 303; 422; 404 si la línea no es de esa cotización |
| `POST /cotizaciones/{id}/lineas/{line_id}/eliminar` | Elimina la línea. | 303; 404 |
| `POST /cotizaciones/{id}/entrega` | Guarda `date`, `time`, `mode` y `address`; al guardar se quitan las marcas «por confirmar» de la fecha y de la modalidad. | 303; 422; 404 |

No existe ninguna ruta ni ningún campo de formulario para escribir un precio (FR-014). Un campo
`price` o `unit_price` enviado a mano se ignora, porque los modelos de entrada no lo tienen; una
prueba lo verifica.

## Detalle de una cotización

- **Encabezado**:
  - «Cotización n.º {id}» y el estado «Borrador»;
  - la fecha de creación en hora de Colombia;
  - si hay líneas pendientes, «Incompleta: {n} línea(s) por revisar».
- **Aviso de la IA**, según `ai_outcome`. Ningún aviso tiene detalles técnicos:

  | `ai_outcome` | Aviso |
  |---|---|
  | `ok` | ninguno |
  | `timeout` | «La IA no respondió a tiempo: agrega los productos a mano» |
  | `provider_error` | «La IA no está disponible en este momento: agrega los productos a mano» |
  | `invalid_output` | «La IA no entregó una respuesta válida: agrega los productos a mano» |
  | `disabled` | «La IA está desactivada en este ambiente: agrega los productos a mano» |

- **Mensaje del cliente**: el texto original, en un bloque de solo lectura.
- **Tabla de líneas**: producto y variante (`label`), cantidad, precio unitario, subtotal y
  acciones.
  - **Línea «Por revisar»**: muestra la insignia «Por revisar», el motivo y el texto del cliente,
    sin precio ni subtotal. Incluye un formulario para elegir el ítem (un `<select>` con
    `list_quotable_items`) y la cantidad.
  - **Cantidad asumida**: la marca «Cantidad supuesta: confírmala».
- **Total**: la suma de las líneas listas, en pesos con separador de miles («$ 45.000»). Si hay
  pendientes, el aviso «No incluye las líneas por revisar».
- **Formulario «Agregar producto»**: un `<select>` de ítems cotizables y la cantidad.
- **Formulario de entrega**: fecha, hora, modalidad y dirección. «Por confirmar» aparece junto a
  la fecha o la modalidad marcadas.
- **Ancho**: la página es usable a 360 px. En pantallas angostas, la tabla se vuelve una lista
  apilada.

## Mensajes de validación

| Caso | Mensaje |
|---|---|
| Mensaje vacío | «Pega el mensaje del cliente» |
| Mensaje largo | «El mensaje es demasiado largo (máximo 2.000 caracteres)» |
| Cantidad no válida | «La cantidad debe ser un número entero entre 1 y 999» |
| Ítem ya no cotizable | «Ese producto ya no está disponible en el catálogo» |
| Fecha inválida | «Escribe una fecha válida» |
| Hora inválida | «Escribe una hora válida (HH:MM)» |
