# Plan de implementación: PED-88 · HU-15 Catálogo de productos

**Rama**: `feature/PED-88-catalogo-productos` | **Fecha**: 2026-11-16 | **Spec**: [spec.md](spec.md)

**Entrada**: especificación de `specs/002-catalogo-productos/spec.md`

## Resumen

Catálogo de productos y variantes con precios enteros en COP, administrable desde páginas HTML.
Enfoque:
- **Modelos**: `Product` y `ProductVariant` (SQLModel), creados con la primera migración de
  Alembic, que entra en esta historia.
- **Unicidad**: entre activos, con clave normalizada (sin mayúsculas, tildes ni espacios sobrantes)
  e índice único parcial.
- **Validación del precio**: como texto. Solo dígitos, opcionalmente agrupados de a tres con
  punto o espacio («45.000» = «45 000» = 45000). «45.00», «4.5» y la coma se rechazan con
  mensajes claros. El máximo holgado es 100.000.000, con un mensaje de posible error de
  digitación.
- **Capas**: router → servicio → repositorio, con errores de dominio traducidos a 404 y 409.
- **Formularios**: HTML clásicos con Post/Redirect/Get.
- **Fuente de precios**: el servicio expone `list_quotable_items`, la única fuente de precios para
  las historias de cotización y del bot.

Decisiones en [research.md](research.md).

## Contexto técnico

**Lenguaje/versión**: Python 3.12 (uv)

**Dependencias principales**: FastAPI, SQLModel, pydantic-settings, Jinja2 y python-multipart
(ya incluidos con `fastapi[standard]`); **nueva**: `alembic` (R1). Pico.css desde CDN, con versión
fija.

**Almacenamiento**: SQLite (local: archivo; pruebas: memoria) y PostgreSQL en Neon (producción);
tablas `product` y `product_variant`

**Pruebas**: pytest. `tests/unit` cubre la normalización, la validación del precio, el precio
efectivo y el servicio sobre SQLite en memoria. `tests/integration` cubre las páginas con
`TestClient` y las migraciones contra los modelos sobre SQLite en memoria (R2).

**Plataforma**: servicio web en Render (runtime nativo de Python + uv)

**Tipo de proyecto**: servicio web (monolito FastAPI en capas, con plantillas del lado del
servidor)

**Metas de rendimiento**: listado de 500 productos en menos de 2 s (SC-006), sin paginación

**Restricciones**: montos enteros, sin `float`; sin `create_all` fuera de las pruebas; sin red en
las pruebas; interfaz usable a 360 px; `mypy --strict`; cobertura ≥ 80 % con ramas

**Escala/alcance**: 1 usuario; cientos de productos; ~10 archivos de código, 5 plantillas, 1
migración y ~5 archivos de prueba

## Verificación de la constitución

*Puerta: antes de la Fase 0 y de nuevo tras la Fase 1.*

| Principio | Cumplimiento | Estado |
|---|---|---|
| I. TDD | En `tasks.md`, cada tarea irá precedida de su prueba; commits `test` → `feat` → `refactor` | ✅ |
| II. Pruebas deterministas | SQLite en memoria con `create_all` solo en las pruebas; migraciones probadas también sobre SQLite en memoria, con la conexión pasada a Alembic; sin red ni IA; nada depende de la fecha | ✅ |
| III. Calidad | Sin cambios en la configuración de ruff, mypy ni cobertura | ✅ |
| IV. Stack y YAGNI | SQLModel + Alembic; Jinja2 + Pico.css sin frameworks de frontend; precios `int`; una sola dependencia nueva (`alembic`), justificada (R1); sin HTMX mientras no haga falta (R7); router → service → repository | ✅ |
| V. La IA asiste | Sin IA en esta historia; `list_quotable_items` es la única fuente de precios, para que la IA nunca los fije (R10) | ✅ |
| VI. Seguridad y privacidad | Sin secretos nuevos; Jinja2 escapa la salida (nombres y descripciones son texto del usuario); sin datos personales en logs. El catálogo queda sin login hasta HU-07 (ver riesgos) | ✅ con riesgo anotado |
| VII. Trazabilidad | Rama `feature/PED-88-…`; commits `tipo(PED-88): …` | ✅ |

**Tras el diseño (Fase 1)**: sin cambios; ninguna violación. La tabla de complejidad queda vacía.

## Estructura del proyecto

### Documentación (esta funcionalidad)

```text
specs/002-catalogo-productos/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── catalog-pages.md
│   └── catalog-service.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Código fuente

```text
alembic.ini                    # NUEVO
migrations/                    # protegida por .claude/hooks/guard_files.py
├── env.py                     # NUEVO: URL desde Settings, build_engine, SQLModel.metadata, batch en SQLite
├── script.py.mako             # NUEVO (plantilla de Alembic)
└── versions/
    ├── xxxx_crear_tabla_de_productos.py  # NUEVO (US1): product, índice parcial, CHECK
    └── yyyy_crear_tabla_de_variantes.py  # NUEVO (US2): product_variant, índice parcial, CHECK

app/
├── main.py                    # MODIFICAR: incluir el router del catálogo
├── templating.py              # NUEVO: Jinja2Templates + filtro cop (5000 → "$ 5.000")
├── models/
│   ├── __init__.py            # NUEVO: exporta los modelos (lo importa migrations/env.py)
│   └── catalog.py             # NUEVO: parse_price, normalize_key, clean_text, VariantKind, Product, ProductVariant, ProductInput, VariantInput, QuotableItem
├── repositories/
│   ├── __init__.py            # NUEVO
│   └── catalog.py             # NUEVO: consultas y persistencia
├── services/
│   └── catalog.py             # NUEVO: effective_price, unicidad, activación, errores de dominio, list_quotable_items
├── routers/
│   └── catalog.py             # NUEVO: páginas /productos (contrato catalog-pages)
└── templates/
    ├── base.html              # NUEVO: Pico.css, viewport, navegación
    └── catalog/
        ├── list.html          # NUEVO
        ├── detail.html        # NUEVO: variantes + formulario para agregar una
        ├── product_form.html  # NUEVO: crear y editar
        └── variant_form.html  # NUEVO: editar variante

tests/
├── conftest.py                # MODIFICAR: fixtures session (SQLite en memoria + create_all) y client
├── unit/
│   ├── test_catalog_rules.py    # NUEVO: normalize_key, precio (45.000 / 45 000 / 45000 / 45,5), campos, effective_price
│   ├── test_templating.py       # NUEVO: filtro cop y plantilla base
│   └── test_catalog_service.py  # NUEVO: CRUD, unicidad, activar/desactivar, list_quotable_items
└── integration/
    ├── test_catalog_pages.py    # NUEVO: rutas, 303/422/409/404, mensajes, formato $ 5.000
    └── test_migrations.py       # NUEVO: upgrade head = modelos; downgrade base

docs/despliegue.md             # MODIFICAR: Start Command con alembic upgrade head
```

**Decisión de estructura**: se completa la arquitectura en capas que fija la constitución
(`app/models`, `app/repositories` y `app/templates` aparecen por primera vez), con pruebas en
`tests/unit` y `tests/integration`.

## Notas para `/speckit-tasks`

- **Orden sugerido por historia**:
  - **Historia 1 (P1)**: normalización y validación → modelos y migración (con su prueba R2) →
    repositorio y servicio de producto → páginas de crear y listar.
  - **Historia 2 (P2)**: variantes y precio efectivo → `list_quotable_items`.
  - **Historia 3 (P3)**: editar, desactivar y reactivar.
- **Equivalencias con Spring**: `ProductInput` es el DTO con Bean Validation; el servicio es el
  `@Service`; los errores de dominio se traducen en el router como un `@ExceptionHandler`;
  Alembic es Flyway.
- **Fixtures**:
  - `session`: motor SQLite en memoria (`build_engine("sqlite://")`) + `SQLModel.metadata.
    create_all`.
  - `client`: `create_app(test_settings)`, ejecuta `create_all` sobre `app.state.engine` y crea un
    `TestClient`.
- **Prueba de migraciones**: `Config` con la ruta de `alembic.ini` calculada desde la raíz del
  repositorio, y `cfg.attributes["connection"]` con una conexión sobre `build_engine("sqlite://")`;
  `env.py` usa esa conexión si viene dada, en vez de leer `Settings` (R2).
- **Índices parciales**: declararlos en `__table_args__` con `sqlite_where` y `postgresql_where`,
  para que la prueba de R2 no encuentre diferencias.
- **Formularios**: leer con `Annotated[str, Form()]` y construir el `*Input`; si hay errores,
  volver a mostrar la plantilla con el estado 422 o 409. Una casilla sin marcar no llega en el
  formulario, así que `tracks_inventory` vale `False` por defecto.

## Riesgos y pasos manuales

- **Catálogo sin login en producción**: hasta HU-07 (PED-15, Sprint 3), cualquiera que conozca la
  URL podría modificar el catálogo. Opciones: no publicar el enlace o no desplegar a producción
  las páginas del catálogo hasta entonces. Decisión del dueño del producto; no bloquea esta
  historia.
- **Render**: antes de integrar en `main`, cambiar el Start Command a `uv run --no-sync alembic
  upgrade head && uv run --no-sync fastapi run app/main.py --host 0.0.0.0 --port $PORT` (ya
  previsto en `docs/despliegue.md`). Si no, la app arranca sin tablas.
- **Pico.css por CDN**: si el CDN no responde, la página funciona pero sin estilos; aceptable
  para el alcance.

## Seguimiento de complejidad

Sin violaciones que justificar.
