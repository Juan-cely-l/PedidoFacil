# Investigación: PED-88 · HU-15 Catálogo de productos

Decisiones técnicas tomadas para el plan. Ninguna queda marcada como pendiente de aclarar.

## R1. Primeras tablas: Alembic entra en esta historia

- **Decisión**: agregar `alembic` (`uv add alembic`), con `alembic.ini` en la raíz y el directorio
  `migrations/` (la ruta que protege `.claude/hooks/guard_files.py`). `env.py` toma la URL de `Settings` y reutiliza `build_engine` de `app/db.py`, así
  local (SQLite) y producción (Neon) siguen la misma regla de driver y timeout. `target_metadata =
  SQLModel.metadata`, importando `app.models` para registrar las tablas. Para SQLite se activa
  `render_as_batch=True`, porque SQLite no admite la mayoría de `ALTER TABLE`.
- **Justificación**: la constitución prohíbe `create_all` fuera de las pruebas, y el plan de
  PED-11 dejó Alembic explícitamente para esta historia. El arranque en Render ya prevé
  `alembic upgrade head` antes de `fastapi run` (`docs/despliegue.md`).
- **Alternativas**: `create_all` al arrancar, que la constitución prohíbe; SQL a mano, que pierde
  el autogenerate y el historial de versiones.

## R2. Las migraciones se prueban contra los modelos

- **Decisión**: una prueba de integración ejecuta `alembic upgrade head` sobre SQLite **en
  memoria** (constitución, principio II). `migrations/env.py` usa la conexión que reciba en
  `config.attributes["connection"]` (receta de la documentación de Alembic) y solo crea su propio
  motor si no recibe ninguna. La prueba abre una conexión sobre `build_engine("sqlite://")`, se la
  pasa a Alembic y compara el esquema resultante con `SQLModel.metadata`
  (`alembic.autogenerate.compare_metadata`). Debe dar cero diferencias. También ejecuta
  `downgrade base` para verificar que la migración se puede revertir.
- **Justificación**: el resto de las pruebas usan `create_all`; sin esta prueba, un modelo
  cambiado sin su migración pasaría la CI y fallaría en producción.
- **Alternativas**: revisar las migraciones a mano, sin garantía automática.

## R3. Unicidad: índice único parcial más verificación en el servicio

- **Decisión**: cada tabla guarda una clave normalizada (`name_key` en producto, `value_key` en
  variante). Hay un índice único parcial `WHERE is_active` sobre `name_key` y otro sobre
  `(product_id, kind, value_key)`. SQLite y PostgreSQL admiten índices parciales
  (`sqlite_where` / `postgresql_where`). El servicio consulta antes de guardar para dar un mensaje
  claro, y si dos peticiones chocan, traduce la `IntegrityError` del índice al mismo error de
  dominio.
- **Justificación**: los productos inactivos pueden repetir nombre (spec, historia 3, escenario
  5), así que no sirve un `UNIQUE` simple. La base es la garantía final y el servicio da la
  experiencia de usuario.
- **Alternativas**: solo la verificación en el servicio, que deja pasar duplicados con peticiones
  simultáneas; un `UNIQUE` completo, que impide recrear un producto desactivado.

## R4. Normalización de nombres para comparar

- **Decisión**: una función pura `normalize_key(text)` (en `app/models/catalog.py`, junto a `parse_price`, porque los validadores de entrada la usan y los modelos no deben depender de los servicios) recorta los espacios, colapsa los espacios
  internos repetidos, pasa a minúsculas con `casefold()` y quita las tildes (descomposición
  Unicode NFD y eliminación de las marcas combinantes, con `unicodedata` de la biblioteca
  estándar), **salvo la virgulilla de la ñ**: la ñ no es una tilde y cambia la palabra («Piña» ≠
  «Pina», «Año» ≠ «Ano»). Por eso se recompone con NFC antes de quitar marcas, o se protege
  `ñ`/`Ñ` y se quitan las marcas del resto. Lo que se muestra se guarda solo recortado y con los espacios internos colapsados;
  la clave normalizada se usa únicamente para comparar.
- **Justificación**: cumple FR-011 («Té» = «te», «Brownie » = «brownie») sin dependencias nuevas.
  Colapsar los espacios internos evita que «Torta  negra» (dos espacios) pase como distinta.
- **Alternativas**: la librería `unidecode`, dependencia innecesaria; collations de la base de
  datos, que se comportan distinto en SQLite y en PostgreSQL.

## R5. Validación del precio como texto de formulario

- **Decisión**: el formulario recibe el precio como texto y se procesa en dos pasos:
  1. **Forma**: tras recortar, el texto debe ser solo dígitos (`^[0-9]+$`) o dígitos agrupados
     de a tres con punto o espacio como separador de miles (`^[0-9]{1,3}([.\s][0-9]{3})+$`; `\s`
     incluye los espacios no separables U+00A0 y U+202F, frecuentes al copiar de una hoja de
     cálculo). En Colombia «45.000» es la forma natural de escribir cuarenta y cinco mil.
  2. **Valor**: se quitan los separadores y se exige `1 ≤ precio ≤ 100_000_000`.

  La coma nunca se acepta, porque es separador decimal y los pesos no llevan centavos. Un texto
  con solo dígitos, puntos y espacios que no cumple la agrupación («45.00», «4.5», «45000.000»)
  se rechaza con un mensaje propio: quitar los puntos sin más convertiría «45.00» en 4500 en
  silencio.

  Casos de prueba: «45.000», «45 000» y «45000» → 45000; «1.250.000» → 1250000; «45.00», «4.5» →
  mensaje de agrupación; «45,5» y «45,000» → precio inválido. Mensajes:
  - «El precio debe ser un número entero mayor que cero» (vacío, 0, negativo, coma, texto).
  - «Usa el punto solo para separar miles, por ejemplo 45.000; los pesos no llevan centavos»
    (puntos o espacios mal agrupados).
  - «El precio supera 100.000.000; revisa si hay un error de digitación» (por encima del máximo).

  En la variante, el precio vacío significa «usa el precio del producto». La base de datos tiene
  además un `CHECK (price > 0 AND price <= 100000000)`.
- **Justificación**: la conversión flexible de Pydantic a `int` aceptaría formatos ambiguos que la
  spec no prevé («5_000», «5.0» como 5), así que una regla explícita es más predecible. Exigir
  grupos de tres dígitos evita interpretar en silencio un punto decimal como separador de miles.
  El `CHECK` protege contra escrituras fuera del servicio.
- **Alternativas**: `int` con conversión flexible de Pydantic (ambigua); `Decimal`, que la
  constitución descarta: los montos son enteros en pesos.

## R6. Tipos de variante como enumeración

- **Decisión**: `VariantKind(StrEnum)` con los valores `sabor`, `peso`, `color`, `marca` y
  `tamano`, que en la interfaz se muestran como «Sabor», «Peso», «Color», «Marca» y «Tamaño». En
  la base se guarda como texto (`VARCHAR`) con un `CHECK`, sin el tipo `ENUM` nativo de
  PostgreSQL.
- **Justificación**: la spec fija la lista. Guardarla como texto evita migraciones de tipo `ENUM`
  en PostgreSQL si mañana se agrega otro tipo; basta cambiar el `CHECK`.
- **Alternativas**: texto libre, que no cumple FR-005; `ENUM` nativo, más rígido de migrar.

## R7. Interfaz: formularios HTML clásicos, sin HTMX por ahora

- **Decisión**: plantillas Jinja2 con Pico.css (cargado desde jsDelivr con versión fija y
  `integrity`), formularios HTML con `POST` y el patrón Post/Redirect/Get: si todo sale bien,
  `303 See Other`; si hay errores, se vuelve a mostrar el formulario con los valores escritos y
  los mensajes junto a cada campo, con estado `422` (validación) o `409` (duplicado o conflicto
  al reactivar). HTMX no se usa todavía: ninguna pantalla de esta historia necesita
  actualizaciones parciales.
- **Justificación**: HTMX 2 no reemplaza el contenido ante respuestas 4xx sin configuración
  adicional, y aquí no aporta nada (YAGNI, principio IV). Los formularios clásicos funcionan sin
  JavaScript y se prueban directamente con `TestClient`. `jinja2` y `python-multipart` ya llegan
  con `fastapi[standard]`, así que no hay dependencias nuevas para la interfaz.
- **Alternativas**: `hx-boost` con `responseHandling` configurado (más piezas sin beneficio aquí);
  una API JSON más un frontend aparte, que la constitución prohíbe.

## R8. Rutas en español, identificadores en inglés

- **Decisión**: las URL visibles para el dueño están en español (`/productos`,
  `/productos/{id}/variantes`, `…/desactivar`, `…/activar`); funciones, clases y módulos están en
  inglés (`catalog`, `Product`, `ProductVariant`). Como los formularios HTML solo envían `GET` y
  `POST`, editar, desactivar y activar son `POST` a rutas explícitas.
- **Justificación**: cumple las restricciones de idioma de la constitución sin depender de
  JavaScript para enviar `PUT` o `DELETE`.

## R9. Capas y errores de dominio

- **Decisión**:
  - `app/repositories/catalog.py` solo consulta y persiste.
  - `app/services/catalog.py` aplica las reglas (normalización, unicidad, precio efectivo,
    activación) y lanza `ProductNotFoundError`, `VariantNotFoundError`, `DuplicateProductError` y
    `DuplicateVariantError`.
  - El router traduce los errores: no encontrado → `404`, duplicado → `409` con el formulario.
  - El servicio recibe la `Session` por `Depends`, igual que el de health.
- **Justificación**: es la arquitectura en capas que fija la constitución, y los routers no tocan
  repositorios. Equivale en Spring a `@Repository` → `@Service` → `@Controller` con un
  `@ExceptionHandler` por excepción de dominio.
- **Alternativas**: devolver `None` o tuplas de error, que mezcla el control de flujo con los
  datos.

## R10. Fuente de precios para cotizaciones (FR-013)

- **Decisión**: `list_quotable_items(session) -> list[QuotableItem]` en el servicio. Devuelve
  cada producto activo sin variantes activas como un ítem, y cada variante activa de un producto
  activo como otro ítem. Cada ítem trae `product_id`, `variant_id | None`, `label` (por ejemplo,
  «Café — Peso: 500 g») y `unit_price` (precio efectivo, entero).
- **Justificación**: es el único punto que leerán las historias de cotización y del bot; las
  reglas de qué es cotizable (FR-009) y del precio efectivo (FR-006) viven en un solo lugar y se
  prueban con pruebas unitarias. Si un producto tiene variantes activas, se cotiza por variante y
  no como producto suelto, para que el cliente siempre elija una presentación.
- **Alternativas**: que cada historia consulte las tablas directamente, lo que duplica las
  reglas y abre la puerta a precios distintos.

## R11. Datos de pedidos anteriores (FR-010)

- **Decisión**: esta historia no crea pedidos. Lo que garantiza FR-010 aquí es que no existe el
  borrado definitivo, ni en la interfaz ni en el servicio, y que las claves foráneas futuras hacia
  `product` y `product_variant` siempre tendrán a quién apuntar. Las líneas de cotización y de
  pedido (otras historias) guardarán una copia del nombre, la variante y el precio.
- **Justificación**: evita diseñar ahora tablas que pertenecen a otras historias (YAGNI) sin
  cerrar la puerta a cumplir FR-010.
