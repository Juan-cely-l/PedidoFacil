# Modelo de datos: PED-16 · HU-08 Cotización con IA

Montos en pesos enteros (`int`), nunca `float` (principio IV). Fechas de creación en UTC; fecha
de entrega como `date` local de Colombia.

## Tablas nuevas (migración de Alembic)

### `quote`: Cotización

| Campo | Tipo | Reglas |
|---|---|---|
| `id` | int, PK | |
| `status` | texto (≤ 12) | `CHECK status IN ('borrador')`. Es el único estado en esta historia; HU-16 y HU-17 agregan más. |
| `customer_message` | texto (≤ 2000) | Obligatorio, sin espacios al inicio ni al final. Vacío → rechazo antes de llamar a la IA. |
| `created_at` | datetime con zona (UTC) | Lo fija el servicio, con `now` inyectable en las pruebas. |
| `ai_outcome` | texto (≤ 16) | `CHECK IN ('ok','timeout','provider_error','invalid_output','disabled')` (research R4 y R12) |
| `ai_duration_ms` | int, nulo | Duración de la consulta; nulo si fue `disabled`. |
| `delivery_date` | date, nulo | Resuelta por el código (R7). |
| `delivery_date_needs_review` | bool | La fecha coincide con hoy, ya pasó o no se pudo resolver habiendo una mención. |
| `delivery_time` | time, nulo | Normalizada por el código (research R7b). |
| `delivery_time_needs_review` | bool | El cliente mencionó una hora que no se pudo normalizar con seguridad, o una hora de 1 a 6 sin «mañana» ni «tarde». |
| `delivery_mode` | texto (≤ 10), nulo | `CHECK IN ('domicilio','recoger')` |
| `delivery_mode_needs_review` | bool | Hay dirección pero el cliente no dijo la modalidad: se asume `domicilio` y se marca. |
| `delivery_address` | texto (≤ 200), nulo | |

Se calculan al leer, no se guardan:

| Valor | Cálculo |
|---|---|
| `total` | Suma de `subtotal` de las líneas `lista` |
| `pending_count` | Número de líneas `por_revisar` |

Índice: `created_at DESC`, para la lista.

### `quote_line`: Línea de cotización

| Campo | Tipo | Reglas |
|---|---|---|
| `id` | int, PK | |
| `quote_id` | int, FK → `quote.id`, `ON DELETE CASCADE` | Índice. |
| `position` | int | Orden de aparición, desde 1. |
| `customer_text` | texto (≤ 200), nulo | Lo que escribió el cliente. Nulo en las líneas agregadas a mano. |
| `status` | texto (≤ 12) | `CHECK IN ('lista','por_revisar')` |
| `review_reason` | texto (≤ 20), nulo | `no_reconocido`, `falta_variante` o `cantidad_invalida`. Obligatorio si `por_revisar`, nulo si `lista`. |
| `product_id` | int, FK → `product.id`, `RESTRICT`, nulo | |
| `variant_id` | int, FK → `product_variant.id`, `RESTRICT`, nulo | Si hay variante, hay producto. |
| `label` | texto (≤ 200), nulo | Copiado de `QuotableItem.label` al cotizar. |
| `unit_price` | int, nulo | Copiado de `QuotableItem.unit_price` (R9). `CHECK unit_price IS NULL OR unit_price > 0`. |
| `quantity` | int, nulo | `CHECK quantity IS NULL OR quantity BETWEEN 1 AND 999`. |
| `quantity_assumed` | bool | La IA no dio cantidad y se asumió 1. |

Valor calculado: `subtotal = unit_price × quantity`, solo para las líneas `lista`.

**Invariante de línea** (`CHECK` y validación en el servicio):

| `status` | `product_id` | `unit_price` | `quantity` | `label` | `review_reason` |
|---|---|---|---|---|---|
| `lista` | obligatorio | obligatorio | obligatoria | obligatorio | nulo |
| `por_revisar` | opcional (`falta_variante` lo lleva) | nulo | opcional | opcional | obligatorio |

## Transiciones de una línea

```text
(IA) ítem cotizable válido ──────────────────────────────▶ lista
(IA) no reconocido / falta variante / cantidad inválida ─▶ por_revisar
por_revisar ── el dueño elige un ítem cotizable y una cantidad ──▶ lista (precio del catálogo vigente)
lista ── el dueño cambia el producto o la variante ──▶ lista (vuelve a copiar label y unit_price)
lista ── el dueño cambia solo la cantidad ──▶ lista (conserva unit_price)
cualquiera ── eliminar ──▶ (borrada)
```

La cotización está siempre en `borrador` en esta historia.

## Salida de la IA

Modelos Pydantic en `app/services/quote_ai.py`, con `extra="forbid"`. **No tienen ningún campo
de precio, subtotal ni total** (RD-2; lo verifica una prueba).

```text
QuoteExtraction
├── lines: list[ExtractedLine]         (máx. 30)
├── delivery_date: DateExpression | None
├── delivery_time: str | None          (1..40; la expresión de hora tal como la vio, sin formato:
│                                        «a las 3 de la tarde», «9:00»; la normaliza el código, R7b)
├── delivery_mode: "domicilio" | "recoger" | None
└── delivery_address: str | None       (≤ 200)

ExtractedLine
├── customer_text: str                 (1..200; lo que dijo el cliente)
├── product_id: int | None             (id visto en <catalogo>, o null si no está seguro)
├── variant_id: int | None
└── quantity: int | None               (null si el cliente no la dijo)

DateExpression
├── kind: "today" | "offset" | "weekday" | "day_of_month" | "absolute" | "unknown"
├── days: int | None                   (offset: 0..60)
├── weekday: int | None                (0 = lunes … 6 = domingo)
├── day: int | None                    (day_of_month: 1..31)
└── date: "YYYY-MM-DD" | None          (absolute)
```

El código convierte `QuoteExtraction` en filas de `quote` y `quote_line` con las reglas de
research.md R5 (líneas), R7 (fecha) y R7b (hora). `QuoteExtraction` no se guarda.

El paso intermedio es `build_lines(extraction, items) -> list[LineDraft]`, una función pura. Un
`LineDraft` tiene los campos de `quote_line` sin ids de cotización ni de línea: `customer_text`,
`product_id`, `variant_id`, `quantity`, `quantity_assumed`, `status`, `review_reason`, `label` y
`unit_price`. Las dos últimas son `null` si la línea está «Por revisar», y si no, salen del
`QuotableItem`. El banco de mensajes (research R14) puntúa estos `LineDraft`.

## Modelos de entrada (formularios)

Sin campo de precio en ninguno (FR-014).

| Modelo | Campos |
|---|---|
| `QuoteRequestInput` | `message`: obligatorio, 1..2000 caracteres tras `strip()` |
| `LineInput` | `item`: referencia a un ítem cotizable, `"<product_id>"` o `"<product_id>:<variant_id>"`; `quantity`: entero de 1 a 999 |
| `DeliveryInput` | `date` (`YYYY-MM-DD` o vacío), `time` (`HH:MM` o vacío), `mode` (`domicilio`, `recoger` o vacío), `address` (≤ 200 o vacío) |

`LineInput.item` se valida contra `list_quotable_items` al guardar. Si ya no es cotizable, se
rechaza con «Ese producto ya no está disponible en el catálogo».

## Relación con el catálogo existente

- `list_quotable_items` (PED-88) es la **única** fuente de `label` y `unit_price`. No cambia.
- `Product.tracks_inventory` existe en el catálogo, pero esta historia no lo usa (ADR 0004).
