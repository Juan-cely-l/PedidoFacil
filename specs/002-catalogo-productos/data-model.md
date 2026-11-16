# Modelo de datos: PED-88 · HU-15 Catálogo de productos

Las tablas se crean con la primera migración de Alembic (R1). Los montos son enteros en pesos
colombianos (constitución, principio IV).

## Product (tabla `product`)

| Campo | Tipo | Reglas |
|---|---|---|
| `id` | entero, PK | autoincremental |
| `name` | texto (100) | obligatorio; se guarda recortado y con espacios internos colapsados |
| `name_key` | texto (100) | `normalize_key(name)` (R4); se calcula siempre en el servicio, nunca desde el formulario |
| `description` | texto (200) | opcional; cadena vacía si no se indica |
| `price` | entero | `CHECK (price > 0 AND price <= 100000000)` |
| `tracks_inventory` | booleano | obligatorio; por defecto `false` |
| `is_active` | booleano | por defecto `true` |

**Índices**: `ux_product_active_name` único sobre `name_key` `WHERE is_active` (R3).

## ProductVariant (tabla `product_variant`)

| Campo | Tipo | Reglas |
|---|---|---|
| `id` | entero, PK | autoincremental |
| `product_id` | entero, FK → `product.id` | obligatorio; `ON DELETE RESTRICT` (nunca hay borrado definitivo) |
| `kind` | texto (10) | `VariantKind`: `sabor`, `peso`, `color`, `marca`, `tamano`; `CHECK kind IN (...)` (R6) |
| `value` | texto (50) | obligatorio; recortado y con espacios internos colapsados |
| `value_key` | texto (50) | `normalize_key(value)` |
| `price` | entero, nulo | `NULL` = usa el precio del producto; si no es nulo, `CHECK (price > 0 AND price <= 100000000)` |
| `is_active` | booleano | por defecto `true` |

**Índices**:
- `ux_variant_active_kind_value`: único sobre `(product_id, kind, value_key)` `WHERE is_active`.
- `ix_product_variant_product_id`: sobre `product_id`.

**Relación**: un `Product` tiene cero o más `ProductVariant`; una variante pertenece a un solo
producto.

## Reglas derivadas (en el servicio, no en columnas)

- **Precio efectivo de una variante** (FR-006): `variant.price if variant.price is not None else
  product.price`. Se calcula al leer: no se guarda, para que un cambio en el precio del producto
  se refleje en las variantes que no tienen precio propio.
- **Disponible para cotizar** (FR-009): un producto es cotizable si `product.is_active`. Una
  variante es cotizable si `product.is_active and variant.is_active`. Un producto con al menos una
  variante activa se cotiza solo a través de sus variantes (R10).
- **Unicidad** (FR-011): se verifica al crear, al editar y al reactivar, comparando `name_key` (o
  `kind` + `value_key` dentro del producto) contra los registros activos, sin contarse a sí
  mismo.

## Estados

```text
Producto / Variante:  activo ──desactivar──▶ inactivo
                      inactivo ──activar──▶ activo   (rechazado si choca con un activo: 409)
```

Desactivar un producto no cambia el estado guardado de sus variantes; al reactivarlo, cada
variante vuelve con el estado que tenía.

## Objetos de entrada y salida (no son tablas)

- **ProductInput**: `name: str`, `description: str`, `price: str` → validado a `int` (R5),
  `tracks_inventory: bool`. Los errores se devuelven por campo para mostrarlos en el formulario.
- **VariantInput**: `kind: VariantKind`, `value: str`, `price: str` (vacío → `None`; si no, se
  valida como en R5).
- **QuotableItem**: `product_id: int`, `variant_id: int | None`, `label: str`, `unit_price: int`
  (R10).
