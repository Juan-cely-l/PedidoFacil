# Contrato: servicio de catálogo (uso interno)

`app/services/catalog.py` es la interfaz que usarán el router del catálogo y, más adelante, las
historias de cotización y del bot. Todas las funciones reciben una `Session` (inyectada con
`Depends` en los routers).

| Función | Devuelve | Errores |
|---|---|---|
| `list_products(session, include_inactive=False)` | `list[Product]` ordenada por nombre | — |
| `get_product(session, product_id)` | `Product` con sus variantes | `ProductNotFoundError` |
| `create_product(session, data: ProductInput)` | `Product` | `DuplicateProductError` |
| `update_product(session, product_id, data: ProductInput)` | `Product` | `ProductNotFoundError`, `DuplicateProductError` |
| `deactivate_product(session, product_id)` | `Product` | `ProductNotFoundError` |
| `activate_product(session, product_id)` | `Product` | `ProductNotFoundError`, `DuplicateProductError` |
| `add_variant(session, product_id, data: VariantInput)` | `ProductVariant` | `ProductNotFoundError`, `DuplicateVariantError` |
| `update_variant(session, product_id, variant_id, data)` | `ProductVariant` | `VariantNotFoundError`, `DuplicateVariantError` |
| `deactivate_variant(session, product_id, variant_id)` | `ProductVariant` | `VariantNotFoundError` |
| `activate_variant(session, product_id, variant_id)` | `ProductVariant` | `VariantNotFoundError`, `DuplicateVariantError` |
| `effective_price(product, variant)` | `int` | — |
| `list_quotable_items(session)` | `list[QuotableItem]` ordenada por etiqueta | — |

Garantías:
- **Única fuente de precios para cotizar** (FR-013, constitución V): ningún otro módulo calcula
  precios de catálogo.
- `list_quotable_items` nunca incluye productos ni variantes inactivos (FR-009).
- `unit_price` siempre es un `int` entre 1 y 100.000.000.
- La validación de formato (R5) ocurre al construir `ProductInput`/`VariantInput`; el servicio
  recibe datos ya validados.
