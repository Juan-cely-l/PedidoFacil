---
description: "Tareas de PED-88 · HU-15 Catálogo de productos"
---

# Tareas: PED-88 · HU-15 Catálogo de productos

**Entrada**: documentos de diseño en `specs/002-catalogo-productos/`

**Prerrequisitos**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Pruebas**: son obligatorias (TDD, principio I).

- **Rojo**: cada tarea «Prueba» se escribe primero y se ejecuta con `uv run pytest`. DEBE fallar
  por la razón esperada: una aserción o el `NotImplementedError` de un esqueleto, nunca un
  `ImportError` ni un error de sintaxis.
- **Revisión**: tras cada fase roja hay que **detenerse** para que el autor revise la prueba; luego
  commit `test(PED-88): …`.
- **Verde**: tras la implementación, con `uv run pytest`, `uv run ruff check .` y `uv run mypy`
  en verde, commit `feat(PED-88): …`, y `refactor(PED-88): …` si aplica.

**Organización**: por historia de usuario de la spec (US1–US3); cada una se puede probar por
separado.

## Formato: `[ID] [P?] [Historia] Descripción`

- **[P]**: puede hacerse en paralelo (archivos distintos, sin dependencias pendientes)
- **[USn]**: historia de la spec a la que pertenece
- Rutas relativas a la raíz del repositorio

## Convenciones para las pruebas

- **Esqueletos en la fase roja** (como en PED-11): si la prueba usa una función o clase que aún
  no existe, el commit rojo incluye su esqueleto: firma tipada y cuerpo
  `raise NotImplementedError`. Las líneas de prueba que referencian atributos todavía
  inexistentes llevan `# type: ignore[<código>]`, y el commit verde los retira.
- **Fixtures** (en `tests/conftest.py`, desde T006):
  - `session`: `build_engine("sqlite://")` + `SQLModel.metadata.create_all(engine)` +
    `Session(engine)`.
  - `client`: `app = create_app(test_settings)`, `SQLModel.metadata.create_all(app.state.engine)`
    y `TestClient(app)`.

  `create_all` solo se usa aquí, nunca en `app/` (constitución IV).
- **Respuestas de formularios**: en las pruebas de integración, `client.post(...,
  follow_redirects=False)` para comprobar el `303` y la cabecera `Location`.
- **Mensajes**: se comparan con el texto exacto de
  [contracts/catalog-pages.md](contracts/catalog-pages.md).
- **Nombres**: las pruebas se nombran en español (`test_precio_con_puntos_de_miles_se_acepta`);
  los identificadores, en inglés.
- **Errores de validación sin prefijo**: los validadores lanzan
  `pydantic_core.PydanticCustomError("<tipo>", "<mensaje>")`, para que `error["msg"]` sea el
  mensaje en español sin el prefijo «Value error, ».

---

## Fase 1: Preparación

**Propósito**: dependencia, paquetes y esqueleto de Alembic; no cambia el comportamiento.

- [X] T001 Agregar `alembic` con `uv add alembic` (actualiza `pyproject.toml` y `uv.lock`; justificación en research.md R1)
- [X] T002 [P] Crear los paquetes vacíos con docstring en español `app/models/__init__.py` y `app/repositories/__init__.py`, y la carpeta `app/templates/catalog/`
- [X] T003 Configurar Alembic: `alembic.ini` en la raíz (`script_location = migrations`, sin URL fija), `migrations/script.py.mako` y `migrations/env.py`. Si `config.attributes.get("connection")` trae una conexión (la prueba de migraciones pasa una sobre SQLite en memoria, R2), `env.py` la usa directamente en `context.configure(connection=...)`. Si no, toma la URL de `get_settings().database_url` y crea el motor con `build_engine` de `app/db.py`. En ambos casos usa `target_metadata = SQLModel.metadata` tras `import app.models` y activa `render_as_batch=True` cuando el dialecto es SQLite (R1). Verificar `uv run pytest` en verde y hacer commit `chore(PED-88): configurar Alembic`

**Punto de control**: `uv run alembic current` funciona contra la base local sin migraciones.

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: reglas puras de dominio (precio y nombre), plantilla base, formato de pesos y
fixtures.

- [ ] T004 [P] Prueba en `tests/unit/test_catalog_rules.py` para `parse_price(raw: str) -> int` (R5, FR-002), parametrizada con texto exacto del error:
  - Se aceptan: `"45.000"` → 45000, `"45 000"` → 45000, `"45000"` → 45000, `" 45000 "` → 45000, `"1.250.000"` → 1250000, `"45\u00a0000"` y `"45\u202f000"` (espacios no separables) → 45000, `"1"` → 1, `"100.000.000"` → 100000000.
  - Con «Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos»: `"45.00"`, `"4.5"`, `"45000.000"`, `"45.0000"`, `"4.50.000"`, `"45 00"`, `".45"`, `"45."`.
  - Con «El precio debe ser un número entero mayor que cero»: `"45,5"`, `"45,000"`, `""`, `"   "`, `"0"`, `"0.000"`, `"-5"`, `"abc"`, `"5e3"`, `"5_000"`.
  - Con «El precio supera 100.000.000; revisa si hay un error de digitación»: `"100000001"` y `"150.000.000"`.
- [ ] T005 [P] Prueba en `tests/unit/test_catalog_rules.py` para `normalize_key(text: str) -> str` (R4, FR-011): `"  Brownie "` → `"brownie"`; `"Té"` y `"te"` dan la misma clave; `"Torta  Negra"` → `"torta negra"`; `"CAFÉ"` → `"cafe"`; la ñ se conserva: `normalize_key("Piña") == "piña"`, `normalize_key("Piña") != normalize_key("Pina")`, `normalize_key("AÑO") == "año"`; `"Pingüino"` → `"pinguino"`. Agregar también `clean_text(text: str) -> str`, que recorta y colapsa los espacios internos sin cambiar mayúsculas ni tildes: `"  Torta   Negra "` → `"Torta Negra"`
- [ ] T006 [P] Prueba en `tests/unit/test_templating.py`: el filtro `cop` da `5000` → `"$ 5.000"`, `45000` → `"$ 45.000"`, `1250000` → `"$ 1.250.000"` y `1` → `"$ 1"`; `templates.get_template("base.html")` renderiza con `<meta name="viewport" content="width=device-width, initial-scale=1">`, el enlace de Pico.css con versión fija e `integrity`, y `lang="es"`. Agregar las fixtures `session` y `client` a `tests/conftest.py` (ver convenciones)
- [ ] T007 Implementar `parse_price`, `normalize_key` y `clean_text` en `app/models/catalog.py`. `parse_price` recorta y luego acepta `fullmatch(r"[0-9]+")` o `fullmatch(r"[0-9]{1,3}(?:[.\s][0-9]{3})+")` (`\s` cubre U+00A0 y U+202F). Si el texto solo tiene dígitos, puntos y espacios pero no cumple la agrupación, lanza el mensaje de agrupación; en cualquier otro caso, el de precio inválido. Después quita los separadores y exige `1 ≤ n ≤ 100_000_000`. Todos los errores son `PydanticCustomError`. `normalize_key` = `clean_text` + `casefold()` + NFD, quitando las marcas combinantes excepto la virgulilla (U+0303) que sigue a una `n`, y recomponiendo con NFC (la ñ se conserva). Definir las constantes `MAX_PRICE = 100_000_000` y los mensajes como constantes del módulo
- [ ] T008 Implementar `app/templating.py` (`templates = Jinja2Templates(directory="app/templates")` con el filtro `cop`, que usa punto como separador de miles sin depender del `locale` del sistema) y `app/templates/base.html` (Pico.css 2 desde jsDelivr con versión fija e `integrity`, viewport, `lang="es"`, navegación con enlace a «Productos», bloque `content`)

**Punto de control**: reglas de precio y nombre probadas; plantilla base lista.

---

## Fase 3: Historia 1 - Registrar y consultar productos (P1) 🎯 MVP

**Objetivo**: crear productos y verlos en el listado y en el detalle, con validación del precio y
sin nombres activos repetidos.

**Prueba independiente**: con `TestClient`, crear un producto desde `/productos` y verlo en el
listado con su precio formateado.

### Pruebas de la Historia 1 ⚠️

- [ ] T009 [P] [US1] Prueba en `tests/unit/test_catalog_rules.py` para `ProductInput` (data-model.md):
  - `name` se guarda con `clean_text`; vacío o solo espacios → «El nombre es obligatorio»; más de 100 caracteres → «El nombre admite máximo 100 caracteres».
  - `description` es opcional (por defecto `""`) y con más de 200 caracteres → «La descripción admite máximo 200 caracteres».
  - `price` (texto) pasa por `parse_price`: `"45.000"` → `45000` y `"45,5"` → error en el campo `price`.
  - `tracks_inventory` vale `False` por defecto.
  - Si varios campos fallan, `ValidationError.errors()` trae un error por campo, con `loc` igual al nombre del campo.
- [ ] T010 [P] [US1] Prueba en `tests/integration/test_migrations.py` (R2, SQLite en memoria según el principio II):
  - Preparación: `cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))`, para no depender del directorio de trabajo; `engine = build_engine("sqlite://")`; dentro de `with engine.begin() as conn:`, asignar `cfg.attributes["connection"] = conn`.
  - `command.upgrade(cfg, "head")` deja la tabla `product`, y `compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)` devuelve `[]`.
  - Insertar con SQL un `product` con `price = 0` dentro de `conn.begin_nested()` lanza `IntegrityError` (CHECK).
  - `command.downgrade(cfg, "base")` deja la base sin tablas del catálogo.
- [ ] T011 [P] [US1] Prueba en `tests/unit/test_catalog_service.py` (fixture `session`, contracts/catalog-service.md):
  - `create_product` guarda el `name_key` normalizado y `is_active=True`.
  - Un segundo «brownie » activo → `DuplicateProductError`.
  - Un producto inactivo (marcado `is_active=False` directamente en la sesión) no impide crear otro con el mismo nombre.
  - `list_products` devuelve los activos ordenados por nombre sin distinguir mayúsculas; con `include_inactive=True` incluye los inactivos.
  - `get_product(session, 999)` → `ProductNotFoundError`.
  - Dos guardados simultáneos: con `monkeypatch.setattr(repositories.catalog, "find_active_product_by_key", lambda *a, **k: None)`, crear «Brownie» dos veces. El segundo choca con el índice parcial (`IntegrityError`) y el servicio lanza `DuplicateProductError`; la sesión sigue usable después (se hizo `rollback`).
- [ ] T012 [P] [US1] Prueba en `tests/integration/test_catalog_pages.py` (fixture `client`, contracts/catalog-pages.md):
  - `GET /productos` sin productos → 200 con un texto de lista vacía y enlace a `/productos/nuevo`.
  - `GET /productos/nuevo` → 200 con los campos `name`, `description`, `price` y `tracks_inventory`.
  - `POST /productos` válido → 303 con `Location: /productos/{id}`, y el detalle muestra nombre, descripción, `$ 45.000` y «Controla inventario: sí».
  - Parametrizado `price` en `"45.000"`, `"45 000"` y `"45000"` → 303 y el detalle muestra `$ 45.000`.
  - `"45,5"` → 422 con «El precio debe ser un número entero mayor que cero», y el formulario conserva `name` y el texto `45,5`.
  - `"150.000.000"` → 422 con «El precio supera 100.000.000; revisa si hay un error de digitación».
  - `name` vacío → 422 con «El nombre es obligatorio».
  - Nombre activo repetido («BROWNIE») → 409 con «Ya existe un producto activo con ese nombre».
  - `GET /productos/999` → 404.
  - El listado ordena por nombre y muestra el precio con formato `$`.
  - Un nombre `<script>alert(1)</script>` se muestra escapado (`&lt;script&gt;`).

### Implementación de la Historia 1

- [ ] T013 [US1] Implementar en `app/models/catalog.py`:
  - `Product(SQLModel, table=True)`, tabla `product`, según data-model.md:
    - `id`: entero, PK.
    - `name` y `name_key`: `max_length=100`.
    - `description`: `max_length=200`, default `""`.
    - `price`: `int`.
    - `tracks_inventory` y `is_active`: `bool`.
    - `__table_args__`: `CheckConstraint("price > 0 AND price <= 100000000", name="ck_product_price_range")` y `Index("ux_product_active_name", "name_key", unique=True, sqlite_where=text("is_active"), postgresql_where=text("is_active"))`.
  - `ProductInput(BaseModel)` con los validadores de T009.
  - Exportar ambos en `app/models/__init__.py`.
- [ ] T014 [US1] Generar la migración con `uv run alembic revision --autogenerate -m "crear tabla de productos"` en `migrations/versions/`. Revisarla a mano: índice parcial con `sqlite_where`/`postgresql_where`, CHECK con nombre y `downgrade` que borra índice y tabla
- [ ] T015 [US1] Implementar `app/repositories/catalog.py`: `get_product(session, product_id) -> Product | None`, `list_products(session, include_inactive: bool) -> list[Product]` (orden por `name_key`), `find_active_product_by_key(session, name_key, exclude_id: int | None) -> Product | None` y `save(session, obj) -> obj` (`add` + `commit` + `refresh`)
- [ ] T016 [US1] Implementar `app/services/catalog.py`: los errores de dominio `ProductNotFoundError` y `DuplicateProductError`, y las funciones `create_product`, `list_products` y `get_product` según contracts/catalog-service.md. Al crear, verifica duplicados con `find_active_product_by_key`; al guardar, captura `IntegrityError`, hace `rollback` y lanza `DuplicateProductError`
- [ ] T017 [US1] Implementar `app/routers/catalog.py`:
  - Rutas `GET /productos`, `GET /productos/nuevo`, `POST /productos` y `GET /productos/{product_id}`.
  - El formulario se lee con `Annotated[str, Form()]`; `tracks_inventory` es `Annotated[bool, Form()] = False`.
  - Se construye `ProductInput`; un `ValidationError` se convierte en un diccionario `{campo: mensaje}` y se responde 422 con la plantilla y los valores escritos. `DuplicateProductError` → 409; `ProductNotFoundError` → 404.
  - La sesión llega por `Depends(get_session)`.
  - Plantillas `app/templates/catalog/list.html` (lista apilada sin tabla ancha, para 360 px), `product_form.html` (crear; mensajes junto a cada campo con `aria-invalid` y `<small>`) y `detail.html`.
  - Registrar el router en `app/main.py`.

**Punto de control**: US1 completa y probada sola; `uv run alembic upgrade head` crea `product`.

---

## Fase 4: Historia 2 - Variantes con precio propio (P2)

**Objetivo**: variantes de tipo sabor, peso, color, marca o tamaño, con precio propio opcional;
precio efectivo; lista de ítems cotizables (FR-013).

**Prueba independiente**: crear «Café» con dos variantes, una con precio propio y otra sin él, y
comprobar el precio efectivo en el detalle y en `list_quotable_items`.

### Pruebas de la Historia 2 ⚠️

- [ ] T018 [P] [US2] Prueba en `tests/unit/test_catalog_rules.py` para `VariantInput` y `effective_price`:
  - `kind` acepta `sabor`, `peso`, `color`, `marca` y `tamano`; otro valor → «Elige un tipo de variante válido».
  - `value` usa `clean_text`; vacío → «El valor de la variante es obligatorio»; más de 50 caracteres → «El valor admite máximo 50 caracteres».
  - `price` vacío o con solo espacios → `None`; `"32.000"` → `32000`; `"45,5"` → mensaje de precio inválido.
  - `VariantKind.TAMANO.label == "Tamaño"`.
  - `effective_price(product(price=18000), variant(price=None)) == 18000` y con `variant(price=32000)` da `32000`.
- [ ] T019 [P] [US2] Ampliar `tests/integration/test_migrations.py` (misma conexión en memoria que T010): tras `upgrade head` existe `product_variant`, `compare_metadata` sigue devolviendo `[]` y un `kind` fuera de la lista, insertado con SQL dentro de `conn.begin_nested()`, lanza `IntegrityError`
- [ ] T020 [P] [US2] Prueba en `tests/unit/test_catalog_service.py`:
  - `add_variant` guarda `value_key`.
  - Peso «500 G » repetido en el mismo producto → `DuplicateVariantError`.
  - Color «Negro» y marca «Negro» en el mismo producto se permiten.
  - El mismo peso «500 g» en otro producto se permite.
  - `add_variant` sobre un producto inexistente → `ProductNotFoundError`.
  - Dos guardados simultáneos: con `find_active_variant` reemplazado por `monkeypatch` para que devuelva `None`, una variante repetida lanza `DuplicateVariantError` (traducción de `IntegrityError`).
  - `list_quotable_items`:
    - Un producto activo sin variantes da un ítem con `variant_id=None` y `unit_price` = precio del producto.
    - «Café» con variantes activas da solo sus variantes, con etiqueta `"Café — Peso: 500 g"` y su precio efectivo.
    - Una variante inactiva no aparece, y un producto inactivo no aparece ni él ni sus variantes (estados fijados directamente en la sesión).
    - El orden es por etiqueta.
- [ ] T021 [P] [US2] Ampliar `tests/integration/test_catalog_pages.py`:
  - `POST /productos/{id}/variantes` válido → 303 a `/productos/{id}`, y el detalle muestra «Peso: 250 g — $ 18.000» (sin precio propio) y «Peso: 500 g — $ 32.000».
  - Una variante repetida → 409 con «Ese producto ya tiene una variante activa con ese tipo y valor».
  - `kind=talla` → 422 con «Elige un tipo de variante válido».
  - `price=45,5` → 422, y el formulario de variante conserva `value` y el texto `45,5` (FR-012).
  - En la respuesta 409 por variante repetida, el formulario conserva el tipo y el valor escritos.
  - `POST /productos/999/variantes` → 404.
  - El formulario de variante del detalle ofrece los cinco tipos con sus etiquetas en español.

### Implementación de la Historia 2

- [ ] T022 [US2] Implementar en `app/models/catalog.py`:
  - `VariantKind(StrEnum)` con los valores `sabor`, `peso`, `color`, `marca` y `tamano`, y la propiedad `label` («Sabor», «Peso», «Color», «Marca», «Tamaño»).
  - `ProductVariant(SQLModel, table=True)`, tabla `product_variant`:
    - `product_id`: FK a `product.id` con `ondelete="RESTRICT"` e `index=True`.
    - `kind`: `str`, `max_length=10`.
    - `value` y `value_key`: `max_length=50`.
    - `price`: `int | None`.
    - `is_active`: `bool`.
    - `__table_args__`: `CheckConstraint("price IS NULL OR (price > 0 AND price <= 100000000)", name="ck_variant_price_range")`, `CheckConstraint("kind IN ('sabor','peso','color','marca','tamano')", name="ck_variant_kind")` y `Index("ux_variant_active_kind_value", "product_id", "kind", "value_key", unique=True, sqlite_where=text("is_active"), postgresql_where=text("is_active"))`.
  - Relación `Product.variants` ↔ `ProductVariant.product`.
  - `VariantInput`.
  - `QuotableItem` (`product_id`, `variant_id: int | None`, `label`, `unit_price: int`).
- [ ] T023 [US2] Generar la migración `uv run alembic revision --autogenerate -m "crear tabla de variantes"` y revisarla: CHECK con nombre, índice parcial y `downgrade`
- [ ] T024 [US2] Ampliar `app/repositories/catalog.py` con `find_active_variant(session, product_id, kind, value_key, exclude_id: int | None)` y `list_active_products_with_variants(session)` (carga las variantes con `selectinload` para evitar N+1)
- [ ] T025 [US2] Implementar en `app/services/catalog.py` `DuplicateVariantError`, `add_variant`, `effective_price` y `list_quotable_items` (R10), traduciendo `IntegrityError` como en T016
- [ ] T026 [US2] Agregar a `app/routers/catalog.py` la ruta `POST /productos/{product_id}/variantes` (si hay errores, 422 o 409 renderizando `detail.html` con el formulario de variante y sus mensajes) y, en `detail.html`, la lista de variantes con su precio efectivo (calculado en el router con `effective_price`, nunca en la plantilla) y el formulario para agregar una

**Punto de control**: US1 y US2 funcionan por separado; `list_quotable_items` lista la fuente de
precios.

---

## Fase 5: Historia 3 - Editar y desactivar productos (P3)

**Objetivo**: editar productos y variantes, desactivarlos y reactivarlos sin romper la unicidad.

**Prueba independiente**: editar el precio de «Brownie», desactivarlo y verificar que ya no
figura en el listado ni en `list_quotable_items`.

### Pruebas de la Historia 3 ⚠️

- [ ] T027 [P] [US3] Prueba en `tests/unit/test_catalog_service.py`:
  - `update_product` cambia nombre, descripción, precio y `tracks_inventory`, y recalcula `name_key`.
  - Renombrar con su mismo nombre en otras mayúsculas se permite; renombrar al nombre de otro activo → `DuplicateProductError`.
  - Al cambiar el precio de «Café» de 18000 a 20000, la variante sin precio propio pasa a 20000 en `list_quotable_items` y la de 32000 no cambia.
  - `deactivate_product` → `is_active=False`, y desaparece de `list_products()` y de `list_quotable_items`.
  - `activate_product` lo reactiva; si existe otro activo con el mismo nombre → `DuplicateProductError` y sigue inactivo.
  - `update_variant`, `deactivate_variant` y `activate_variant` siguen las mismas reglas; con `variant_id` de otro producto → `VariantNotFoundError`.
  - Desactivar el producto no cambia el `is_active` guardado de sus variantes.
- [ ] T028 [P] [US3] Ampliar `tests/integration/test_catalog_pages.py`:
  - `GET /productos/{id}/editar` → 200 con los valores actuales (precio sin formato, `45000`).
  - `POST /productos/{id}` válido → 303 y el detalle muestra el cambio; inválido → 422; duplicado → 409; inexistente → 404. En los casos 422 y 409, el formulario conserva lo que se escribió, no los valores guardados (FR-012).
  - Edición de variante con `price=45.00` → 422 con el mensaje de agrupación, conservando lo escrito.
  - `POST /productos/{id}/desactivar` → 303 a `/productos`; el producto no está en `/productos` y sí en `/productos?inactivos=1`, marcado «Inactivo».
  - `POST /productos/{id}/activar` con un activo homónimo → 409 con «Ya existe un producto activo con ese nombre».
  - `GET /productos/{id}/variantes/{vid}/editar` → 200.
  - `POST /productos/{id}/variantes/{vid}` → 303.
  - `POST …/variantes/{vid}/desactivar` y `…/activar` → 303, y el detalle marca la variante «Inactiva».
  - Una variante de otro producto → 404.
  - Sin borrado (FR-008): ninguna ruta de `app.routes` cuyo path empiece por `/productos` acepta el método `DELETE`, ni tiene «eliminar» o «borrar» en su path.

### Implementación de la Historia 3

- [ ] T029 [US3] Implementar en `app/services/catalog.py` `VariantNotFoundError`, `update_product`, `deactivate_product`, `activate_product`, `update_variant`, `deactivate_variant` y `activate_variant` (verificación de unicidad con `exclude_id` propio; reactivación verificada como una creación), y en `app/repositories/catalog.py` `get_variant(session, product_id, variant_id) -> ProductVariant | None` (filtra por ambos ids)
- [ ] T030 [US3] Agregar a `app/routers/catalog.py` las rutas de edición, desactivación y activación de productos y variantes (contracts/catalog-pages.md), y crear `app/templates/catalog/variant_form.html`. Reutilizar `product_form.html` en modo edición (acción y título según haya `product`) y agregar a `detail.html` los botones «Editar», «Desactivar» o «Activar» (formularios `POST`), y a `list.html` el enlace «Ver inactivos» y la marca «Inactivo»

**Punto de control**: las tres historias funcionan por separado.

---

## Fase 6: Pulido y temas transversales

- [ ] T031 [P] Prueba en `tests/integration/test_catalog_pages.py` (SC-006): con 500 productos insertados en la sesión de la app, `GET /productos` responde 200 en menos de 2 s (`time.perf_counter`)
- [ ] T032 [P] Actualizar `docs/despliegue.md`: el Start Command pasa a `uv run --no-sync alembic upgrade head && uv run --no-sync fastapi run app/main.py --host 0.0.0.0 --port $PORT`, y agregar una nota de que el catálogo no tiene login hasta HU-07 (PED-15). Actualizar `README.md` con `uv run alembic upgrade head` antes de `uv run fastapi dev app/main.py` y con la ruta `/productos`
- [ ] T033 Ejecutar `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` y `uv run alembic check` (con la base local migrada); confirmar cobertura ≥ 80 % con ramas
- [ ] T034 Validar a mano [quickstart.md](quickstart.md): recorrido 1–9, incluidas las pantallas a 360 px (SC-005)
- [ ] T035 Paso manual del autor antes de integrar en `main`: cambiar el Start Command en Render (T032) y decidir si se publica el enlace del catálogo antes de HU-07 (riesgo en plan.md)

---

## Dependencias y orden de ejecución

### Entre fases

- **Preparación (F1)** → **Fundamentos (F2)** → historias.
- **US1 (F3)**: depende de F2. Crea `Product`, la primera migración, el repositorio, el servicio y
  el router.
- **US2 (F4)**: depende de US1, porque una variante pertenece a un producto y se agrega desde su
  detalle. Se puede probar sola con productos creados en la fixture.
- **US3 (F5)**: depende de US1 para editar y desactivar productos, y de US2 para las tareas de
  variantes (T029, T030).
- **Pulido (F6)**: tras las historias.

### Dentro de cada historia

- Pruebas (fallan, revisión del autor, commit `test`) → modelos → migración → repositorio →
  servicio → router y plantillas (verde, commit `feat`).
- `app/models/catalog.py` lo editan T007, T013 y T022; `app/services/catalog.py`, T016, T025 y
  T029; `app/routers/catalog.py`, T017, T026 y T030; `tests/unit/test_catalog_rules.py`, T004,
  T005, T009 y T018. No paralelizar tareas que comparten archivo, salvo pruebas del mismo archivo
  escritas juntas en la misma fase roja.

### Oportunidades de paralelismo

- F1: T002 en paralelo con T001.
- F2: T004, T005 (mismo archivo, se escriben juntas) y T006 en paralelo.
- US1: T009, T010, T011 y T012 en paralelo (una sola fase roja, un commit `test`).
- US2: T018, T019, T020 y T021 en paralelo.
- US3: T027 y T028 en paralelo.
- F6: T031 y T032 en paralelo.

## Ejemplo de paralelismo: Historia 1

```text
Fase roja (un commit test(PED-88)):
  T009 tests/unit/test_catalog_rules.py      ProductInput
  T010 tests/integration/test_migrations.py  upgrade/downgrade = modelos
  T011 tests/unit/test_catalog_service.py    crear, listar, duplicados
  T012 tests/integration/test_catalog_pages.py  páginas, 303/422/409/404
Fase verde (secuencial): T013 → T014 → T015 → T016 → T017
```

## Estrategia de implementación

1. **MVP**: F1 + F2 + US1. El dueño ya puede registrar su lista de precios; validar y demostrar.
2. **Incremento 2**: US2. Variantes y `list_quotable_items`, que es lo que necesitan las
   historias de cotización.
3. **Incremento 3**: US3. Mantenimiento del catálogo (editar, desactivar, reactivar).
4. **Pulido**: rendimiento, documentación de despliegue y validación manual.

Commits esperados por historia: `test(PED-88): …` (rojo) → `feat(PED-88): …` (verde) →
`refactor(PED-88): …` (opcional).
