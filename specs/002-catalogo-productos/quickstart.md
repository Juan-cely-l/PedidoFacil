# Validación rápida: PED-88 · HU-15 Catálogo de productos

## Requisitos previos

- `uv sync`
- `.env` copiado de `.env.example` con `ENVIRONMENT=local` (SQLite en archivo).

## Pruebas automáticas

```bash
uv run pytest                      # todo, incluida la prueba de migraciones (R2)
uv run ruff check . && uv run mypy
```

Esperado: todo en verde y cobertura ≥ 80 %.

## Migraciones

```bash
uv run alembic upgrade head        # crea product y product_variant
uv run alembic check               # sin diferencias entre modelos y migraciones
```

## Recorrido manual (`uv run fastapi dev app/main.py` → http://127.0.0.1:8000/productos)

1. Crear «Brownie», «Brownie de chocolate», precio `5000`, «controla inventario» marcado → aparece
   en el listado como `$ 5.000` (historia 1).
2. Crear tres productos con los precios `45.000`, `45 000` y `45000` → los tres quedan en
   `$ 45.000`.
3. Intentar el precio `0`, `45,5` y `abc` → «El precio debe ser un número entero mayor
   que cero», sin perder lo escrito. Intentar `45.00` y `4.5` → «Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos».
4. Intentar el precio `150000000` → «El precio supera 100.000.000; revisa si hay un error de
   digitación».
5. Crear «Café» a `18000`; agregar las variantes peso «250 g» (sin precio) y peso «500 g» a
   `32000` → precios efectivos `$ 18.000` y `$ 32.000`. Cambiar el producto a `20000` → la de
   250 g pasa a `$ 20.000` y la de 500 g no cambia (historia 2).
6. Agregar otra vez peso «500 g » → 409, «Ese producto ya tiene una variante activa con ese tipo
   y valor».
7. Crear « brownie » → 409, «Ya existe un producto activo con ese nombre» (historia 3).
8. Desactivar «Brownie» → desaparece del listado y aparece con `?inactivos=1`. Crear otro
   «Brownie» → se permite. Reactivar el antiguo → 409.
9. Probar las pantallas a 360 px de ancho (herramientas de desarrollo del navegador) → sin
   desplazamiento horizontal (SC-005).

## Contratos

- Páginas y mensajes: [contracts/catalog-pages.md](contracts/catalog-pages.md)
- Servicio interno: [contracts/catalog-service.md](contracts/catalog-service.md)
- Modelo: [data-model.md](data-model.md)
