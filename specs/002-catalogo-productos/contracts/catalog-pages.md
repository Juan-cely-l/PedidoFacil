# Contrato: páginas del catálogo

Respuestas HTML (Jinja2 + Pico.css). Los formularios envían
`application/x-www-form-urlencoded`. En esta historia no hay autenticación: el login es HU-07
(PED-15, Sprint 3).

Convenciones:
- Éxito en un `POST` → `303 See Other` hacia el detalle del producto o hacia el listado (patrón
  Post/Redirect/Get).
- Error de validación → `422`, con el mismo formulario, los valores escritos y el mensaje en
  español junto al campo.
- Duplicado, o conflicto al reactivar → `409`, con el formulario o la página de detalle y el
  mensaje.
- Producto o variante inexistente, o variante que no pertenece a ese producto → `404`.

| Método | Ruta | Uso | Respuesta |
|---|---|---|---|
| GET | `/productos` | Listado de productos activos, ordenado por nombre (nombre, precio, «controla inventario») | 200 |
| GET | `/productos?inactivos=1` | Incluye los inactivos, marcados como tales | 200 |
| GET | `/productos/nuevo` | Formulario vacío | 200 |
| POST | `/productos` | Crear producto | 303 → `/productos/{id}` · 422 · 409 |
| GET | `/productos/{id}` | Detalle: datos, variantes con su precio efectivo y formulario para agregar una variante | 200 · 404 |
| GET | `/productos/{id}/editar` | Formulario con los datos actuales | 200 · 404 |
| POST | `/productos/{id}` | Guardar la edición | 303 → `/productos/{id}` · 422 · 409 · 404 |
| POST | `/productos/{id}/desactivar` | Desactivar producto | 303 → `/productos` · 404 |
| POST | `/productos/{id}/activar` | Reactivar producto | 303 → `/productos/{id}` · 409 · 404 |
| POST | `/productos/{id}/variantes` | Agregar variante | 303 → `/productos/{id}` · 422 · 409 · 404 |
| GET | `/productos/{id}/variantes/{vid}/editar` | Formulario de variante | 200 · 404 |
| POST | `/productos/{id}/variantes/{vid}` | Guardar la variante | 303 → `/productos/{id}` · 422 · 409 · 404 |
| POST | `/productos/{id}/variantes/{vid}/desactivar` | Desactivar variante | 303 → `/productos/{id}` · 404 |
| POST | `/productos/{id}/variantes/{vid}/activar` | Reactivar variante | 303 → `/productos/{id}` · 409 · 404 |

## Campos de formulario

**Producto**: `name` (texto), `description` (texto), `price` (texto; solo dígitos, opcionalmente
agrupados de a tres con punto o espacio: «45.000» = «45 000» = «45000»; «45.00» y la coma se
rechazan),
`tracks_inventory` (casilla; si no se envía, vale `false`).

**Variante**: `kind` (`sabor` | `peso` | `color` | `marca` | `tamano`), `value` (texto), `price`
(texto; vacío = usa el precio del producto).

## Mensajes (texto exacto, lo verifican las pruebas)

| Caso | Mensaje |
|---|---|
| Nombre vacío | «El nombre es obligatorio» |
| Nombre de más de 100 caracteres | «El nombre admite máximo 100 caracteres» |
| Descripción de más de 200 caracteres | «La descripción admite máximo 200 caracteres» |
| Precio inválido (vacío, 0, negativo, con coma como «45,5», texto) | «El precio debe ser un número entero mayor que cero» |
| Precio con puntos o espacios mal agrupados («45.00», «4.5») | «Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos» |
| Precio > 100.000.000 | «El precio supera 100.000.000; revisa si hay un error de digitación» |
| Nombre de producto duplicado | «Ya existe un producto activo con ese nombre» |
| Tipo de variante inválido | «Elige un tipo de variante válido» |
| Valor de variante vacío | «El valor de la variante es obligatorio» |
| Valor de más de 50 caracteres | «El valor admite máximo 50 caracteres» |
| Variante duplicada | «Ese producto ya tiene una variante activa con ese tipo y valor» |

## Presentación

- Los precios se muestran en formato colombiano: `$ 5.000`.
- La interfaz se usa completa a 360 px de ancho, sin desplazamiento horizontal (SC-005).
