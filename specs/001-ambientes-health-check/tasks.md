---
description: "Tareas de PED-11 · HU-03 Ambientes y health check"
---

# Tareas: PED-11 · HU-03 Ambientes y health check

**Entrada**: documentos de diseño en `specs/001-ambientes-health-check/`

**Prerrequisitos**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Pruebas**: obligatorias (TDD, principio I). Cada tarea «Prueba» se escribe primero, se ejecuta con
`uv run pytest` y DEBE fallar por la razón esperada (aserción, no `ImportError` ni error de
sintaxis). **Detenerse tras cada fase roja** para que el autor revise la prueba; luego commit
`test(PED-11): …`. Tras la tarea de implementación, con `uv run pytest`, `uv run ruff check .` y
`uv run mypy` en verde, commit `feat(PED-11): …` (y `refactor(PED-11): …` si aplica).

**Organización**: por historia de usuario de la spec (US1–US4), cada una probable por separado.

## Formato: `[ID] [P?] [Historia] Descripción`

- **[P]**: puede hacerse en paralelo (archivos distintos, sin dependencias pendientes)
- **[USn]**: historia de la spec a la que pertenece
- Rutas relativas a la raíz del repositorio

## Convenciones para las pruebas

- Construir configuraciones explícitas con `Settings(_env_file=None, …)` y `monkeypatch.setenv` /
  `monkeypatch.delenv`; nunca depender del `.env` del desarrollador.
- Fuente única de configuración: cada prueba de endpoints construye su propia app con
  `create_app(settings)` (que guarda `settings` y el motor en `app.state`) y no depende de la caché
  de `get_settings()`. Solo las pruebas de `get_settings()` mismo (T018) llaman a `cache_clear()`.
- Fixtures en `tests/conftest.py`: `test_settings` (`Settings(_env_file=None,
  environment="test")`, desde T006) y `production_settings` (desde T009):
  `environment="production"`, `database_url="postgresql://usuario:clave@host/db"`,
  `secret_key="x" * 32`, `ai_provider="fake"`. Crear el motor de PostgreSQL no abre conexión.
- `git_commit` usa el alias `RENDER_GIT_COMMIT`: en pruebas, fijarlo con
  `monkeypatch.setenv("RENDER_GIT_COMMIT", …)` antes de construir `Settings`.
- Dobles de sesión: clase tipada `FailingSession(Session)` (en `tests/conftest.py`) que sobrescribe
  `exec` y `execute` con las mismas firmas y lanza `sqlalchemy.exc.OperationalError`; así pasa
  `mypy --strict`.
- Nombres de pruebas en español (`test_produccion_sin_database_url_no_arranca`); identificadores
  en inglés.

---

## Fase 1: Preparación

**Propósito**: dependencias y estructura de carpetas; sin cambio de comportamiento.

- [X] T001 Agregar dependencias con `uv add sqlmodel "psycopg[binary]"` (actualiza `pyproject.toml` y `uv.lock`; justificación en research.md R11)
- [X] T002 [P] Crear paquetes vacíos con docstring en español: `app/routers/__init__.py`, `app/services/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`
- [X] T003 Crear `tests/conftest.py` cuya primera instrucción sea `os.environ["ENVIRONMENT"] = "test"` (antes de cualquier `import app…`) y mover `tests/test_health.py` a `tests/integration/test_health.py` con `git mv`; verificar `uv run pytest` en verde (commit `chore(PED-11): …`)

**Punto de control**: suite en verde con la nueva estructura.

---

## Fase 2: Fundamentos (bloquea todas las historias)

**Propósito**: `Settings` con `database_url` por ambiente, que usan US1–US4.

- [ ] T004 Prueba en `tests/unit/test_config.py`: con `environment="test"`, `database_url` por defecto es `sqlite://`; con `environment="local"`, es `sqlite:///./pedidofacil.db`; un valor explícito se respeta; `ENVIRONMENT=staging` lanza `ValidationError` cuyo mensaje lista `test`, `local` y `production`
- [ ] T005 Implementar en `app/config.py`: `environment: Literal["test", "local", "production"]` (mantener por ahora el default `"local"`; cambia en T010), `database_url: SecretStr | None = None` y un `@model_validator(mode="after")` que la complete según el ambiente (data-model.md). Refactor sin cambio de comportamiento (la prueba de humo sigue en verde): quitar el campo `app_name` de `Settings` y crear la constante `APP_NAME = "PedidoFácil"` en `app/__init__.py`, usada como `title` en `app/main.py`
- [ ] T006 Agregar a `tests/conftest.py` la fixture `test_settings` (`Settings(_env_file=None, environment="test")`)

**Punto de control**: fundamentos listos; las historias pueden empezar.

---

## Fase 3: Historia 1 - Producción no arranca mal configurada (P1) 🎯 MVP

**Objetivo**: en `production`, el arranque falla nombrando todas las variables ausentes o
inválidas, sin mostrar valores, y con la sugerencia para desarrollo local.

**Prueba independiente**: construir `Settings` de producción con combinaciones inválidas y
comprobar el error; con una válida, crear la app.

### Pruebas de la Historia 1 ⚠️

- [ ] T007 [P] [US1] Prueba en `tests/unit/test_config.py` (validaciones de producción, FR-001, FR-004–FR-008): sin `ENVIRONMENT` el ambiente es `production`; sin `DATABASE_URL` → error que nombra `DATABASE_URL`; `DATABASE_URL="sqlite:///x.db"` → error que exige PostgreSQL; `postgresql://` y `postgres://` se aceptan; sin `SECRET_KEY` → error; `SECRET_KEY` de 31 caracteres → error que menciona «32»; de 32 → aceptada; `AI_PROVIDER` ausente en producción → `gemini`, y sin `GEMINI_API_KEY` → error que la nombra; `AI_PROVIDER="fake"` en producción no exige clave; `AI_PROVIDER="openai"` → error que lista `fake` y `gemini`; en `local` y `test`, `AI_PROVIDER` por defecto es `fake`; en `local` y `test` sin `SECRET_KEY`, `secret_key` existe, tiene al menos 32 caracteres y difiere entre dos instancias de `Settings` (generada, no fija); variables vacías (`SECRET_KEY=""`) cuentan como ausentes; con las tres faltando, un único error las nombra todas
- [ ] T008 [P] [US1] Prueba en `tests/unit/test_config.py` (privacidad, FR-007, SC-006): con `DATABASE_URL="sqlite:///clave-secreta-db.db"` y `SECRET_KEY="clave-secreta-corta"` en producción, `str(error)` no contiene `clave-secreta`; el mensaje termina con «Para desarrollo local copia .env.example a .env (ENVIRONMENT=local)»; `repr(settings)` válido no contiene el valor de `secret_key` ni de `database_url`
- [ ] T009 [P] [US1] Agregar la fixture `production_settings` a `tests/conftest.py` (ver convenciones) y prueba en `tests/integration/test_startup.py`: `create_app(production_settings)` guarda esa misma instancia en `app.state.settings`; con `ai_provider="fake"`, registra (`caplog`) un mensaje de nivel WARNING que indica que producción usa el proveedor de IA simulado; con `ai_provider="gemini"` y clave válida no hay ese WARNING

### Implementación de la Historia 1

- [ ] T010 [US1] Implementar en `app/config.py`: default `environment="production"`; campos `secret_key: SecretStr | None`, `ai_provider: Literal["fake", "gemini"] | None`, `gemini_api_key: SecretStr | None`; `model_config` con `hide_input_in_errors=True`; validador que trata vacíos como ausentes, completa `ai_provider` («fake» en `local`/`test`, «gemini» en `production`), genera `secret_key` con `secrets.token_urlsafe(48)` si falta en `local`/`test` (ningún valor escrito en el código) y, en `production`, acumula los errores de «`DATABASE_URL`: obligatorio y PostgreSQL», «`SECRET_KEY`: obligatoria, ≥ 32 caracteres» y «`GEMINI_API_KEY`: obligatoria si `ai_provider == "gemini"`» en un solo `ValueError` con la sugerencia final (formato en contracts/configuration.md)
- [ ] T011 [US1] Implementar en `app/main.py` `create_app(settings: Settings | None = None)`, que usa `get_settings()` solo si no recibe una y guarda la instancia en `app.state.settings` (fuente única), y el log WARNING al crear la app cuando `environment == "production"` y `ai_provider == "fake"`

**Punto de control**: US1 completa y probada sola.

---

## Fase 4: Historia 2 - Health checks de vida y de base de datos (P1)

**Objetivo**: `GET /health/live` (sin base) y `GET /health` (`SELECT 1`, 200/503), ambos con
`version` y `commit` (contracts/health.md).

**Prueba independiente**: con `TestClient`, consultar ambos endpoints con la base disponible
(SQLite en memoria) y con la sesión sustituida por una que falla.

### Pruebas de la Historia 2 ⚠️

- [ ] T012 [P] [US2] Prueba en `tests/unit/test_db.py`: `build_engine("postgresql://u:p@h/db").url.drivername == "postgresql+psycopg"`; lo mismo para `postgres://`; `postgresql+psycopg://` no cambia; `build_engine("sqlite://")` permite ejecutar `SELECT 1` desde otro hilo (`check_same_thread=False` + `StaticPool`); crear el motor no abre conexiones; `build_engine` pasa `connect_args={"connect_timeout": 5}` (y `pool_pre_ping=True`) para PostgreSQL y no para SQLite, comprobado sin red sustituyendo con `monkeypatch` el `create_engine` que importa `app.db` por un espía tipado que registra sus argumentos y delega en el original (FR-012, SC-003)
- [ ] T013 [P] [US2] Prueba en `tests/unit/test_health_service.py`: `check_database(session)` devuelve `True` con una sesión real sobre `build_engine("sqlite://")`; devuelve `False` con `FailingSession` (clase tipada que extiende `Session` y lanza `sqlalchemy.exc.OperationalError`, ver convenciones), y el log (`caplog`) no contiene la cadena de conexión con credenciales
- [ ] T014 [P] [US2] Prueba en `tests/integration/test_health.py` (ampliar la existente; cada caso construye su app con `create_app(test_settings)` o con un `Settings` propio): `GET /health` → 200 con exactamente `{"status": "ok", "database": "ok", "version": __version__, "commit": "local"}`; con `app.dependency_overrides[get_session]` devolviendo una `FailingSession` → 503 con `{"status": "error", "database": "error", …}` y sin el texto de la excepción; `GET /health/live` → 200 `{"status": "ok", "version", "commit"}` incluso con `get_session` sustituida por una que falla (y sin llamarla); con `RENDER_GIT_COMMIT="a1b2c3d4e5f6"` fijado antes de construir el `Settings` de esa app, ambos devuelven `commit == "a1b2c3d"`; ninguno exige autenticación

### Implementación de la Historia 2

- [ ] T015 [US2] Implementar `app/db.py`: `build_engine(url: str) -> Engine` (normaliza `postgres://`/`postgresql://` a `postgresql+psycopg://`; PostgreSQL con `connect_args={"connect_timeout": 5}` y `pool_pre_ping=True`; SQLite con `check_same_thread=False` y `StaticPool` si es en memoria) y la dependencia `get_session(request: Request)` que hace `yield` de una `Session` de SQLModel sobre `request.app.state.engine` y la cierra. En `app/main.py`, `create_app` guarda `app.state.engine = build_engine(settings.database_url.get_secret_value())` junto a `app.state.settings` (fuente única; sin `get_engine()` ni caché)
- [ ] T016 [US2] Implementar `app/services/health.py`: `check_database(session: Session) -> bool` que ejecuta `SELECT 1` (`sqlalchemy.text`) y ante `SQLAlchemyError` registra el tipo de error sin la URL y devuelve `False`
- [ ] T017 [US2] Implementar `app/routers/health.py` con `GET /health/live` y `GET /health` (`Depends(get_session)`, 503 vía `JSONResponse` si `check_database` es `False`), leyendo el commit de `Depends(get_app_settings)`, una función en `app/config.py` que devuelve `request.app.state.settings` (nunca `get_settings()`), y la versión de `app.__version__`; incluir el router en `app/main.py` y eliminar el endpoint en línea actual

**Punto de control**: US1 y US2 funcionan por separado; el job `deploy` de la CI sigue leyendo
`commit` de `/health`.

---

## Fase 5: Historia 3 - Pruebas aisladas del `.env` (P2)

**Objetivo**: en `test`, la configuración no lee `.env`; en `local`, sí.

**Prueba independiente**: con un `.env` temporal y `monkeypatch.chdir(tmp_path)`, comparar
`get_settings()` en `test` y en `local`.

### Pruebas de la Historia 3 ⚠️

- [ ] T018 [US3] Prueba en `tests/unit/test_config.py`: en `tmp_path`, escribir `.env` con `LOG_LEVEL=ERROR` y `AI_PROVIDER=gemini`; con `ENVIRONMENT=test` en el proceso, `get_settings()` (tras `cache_clear()`) no toma esos valores; con `ENVIRONMENT=local`, sí; una variable del proceso gana sobre el `.env` en `local`

### Implementación de la Historia 3

- [ ] T019 [US3] Implementar en `app/config.py` que `get_settings()` lea `ENVIRONMENT` de `os.environ` y construya `Settings(_env_file=None)` si vale `test`, o `Settings()` (con `env_file=".env"`) en otro caso (research.md R1)

**Punto de control**: la suite da el mismo resultado con o sin `.env` local (SC-005).

---

## Fase 6: Historia 4 - Valores por defecto según el ambiente (P3)

**Objetivo**: `/docs`, `/redoc` y `/openapi.json` solo fuera de producción; nivel de log DEBUG en
`local` e INFO en `production` y `test`, salvo `LOG_LEVEL` explícito.

**Prueba independiente**: crear la app en cada ambiente y consultar las rutas de documentación;
construir `Settings` y revisar `log_level`.

### Pruebas de la Historia 4 ⚠️

- [ ] T020 [P] [US4] Prueba en `tests/integration/test_docs.py`: con `create_app(test_settings)` y con `create_app(Settings(_env_file=None, environment="local", database_url="sqlite://"))`, `/docs`, `/redoc` y `/openapi.json` → 200; con `create_app(production_settings)` → 404 en las tres
- [ ] T021 [P] [US4] Prueba en `tests/unit/test_config.py`: `log_level` por defecto es `"DEBUG"` en `local`, `"INFO"` en `production` y `"INFO"` en `test`; `LOG_LEVEL=WARNING` se respeta en los tres; y en `tests/integration/test_startup.py`, `create_app` aplica el nivel al logger `pedidofacil` (`logging.getLogger("pedidofacil").getEffectiveLevel()`)

### Implementación de la Historia 4

- [ ] T022 [US4] Implementar en `app/config.py` el default de `log_level` en el validador y la propiedad `docs_enabled`; en `app/main.py`, pasar `docs_url`, `redoc_url` y `openapi_url` como `None` en producción y fijar el nivel con `logging.getLogger("pedidofacil").setLevel(...)` además de `basicConfig` (que no hace nada si el logger raíz ya tiene handlers, como ocurre con pytest)

**Punto de control**: las cuatro historias funcionan por separado.

---

## Fase 7: Pulido y temas transversales

- [ ] T023 Prueba en `tests/unit/test_env_example.py` (FR-016, SC-007): toda variable que lee `Settings` (alias o nombre en mayúsculas de cada campo, excepto `RENDER_GIT_COMMIT`, que define Render) aparece en `.env.example`; `.env.example` contiene `ENVIRONMENT=local`; ninguna línea sin comentar asigna valor a `SECRET_KEY`, `GEMINI_API_KEY` ni `DATABASE_URL` con credenciales; `LOG_LEVEL` está comentado
- [ ] T024 Actualizar `.env.example`: `ENVIRONMENT=local` sin comentar; `LOG_LEVEL` comentado (por defecto según ambiente); `DATABASE_URL`, `SECRET_KEY` (con el comando de generación de contracts/configuration.md), `AI_PROVIDER` (`fake`|`gemini`) y `GEMINI_API_KEY` comentadas con una línea que explique cada una y sus valores admitidos; conservar `ADMIN_PASSWORD_HASH` y el bloque de Telegram (HU-19/HU-20)
- [ ] T025 [P] Actualizar `README.md`: tres ambientes, que `ENVIRONMENT` por defecto es `production`, el paso `cp .env.example .env` antes de `uv run fastapi dev app/main.py`, y los endpoints `/health/live` y `/health`
- [ ] T026 Ejecutar `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy`; confirmar cobertura ≥ 80 % con ramas y revisar que ningún log ni respuesta contenga secretos (si `mypy` rechaza `_env_file`, ajustar el tipado según el plugin de Pydantic)
- [ ] T027 Validar manualmente las secciones 2 y 3 de [quickstart.md](quickstart.md) (local y producción mal configurada)
- [ ] T028 Paso manual del autor antes de integrar en `main`: en Render, Health Check Path = `/health/live` y variables de producción definidas (quickstart.md, sección 4)

---

## Dependencias y orden de ejecución

### Entre fases

- **Preparación (F1)** → **Fundamentos (F2)** → historias.
- **US1 (F3)**: depende solo de F2. Introduce `create_app(settings)` y `app.state.settings` (T011).
- **US2 (F4)**: depende de F2 y de T011 (`create_app(settings)`), pero no de las validaciones de
  producción.
- **US3 (F5)**: depende de F2; T019 solo toca `get_settings()`, que únicamente usa `create_app`
  cuando no recibe configuración.
- **US4 (F6)**: depende de T009 (fixture `production_settings`) y T011; T022 edita `app/main.py`,
  igual que T011 y T015/T017: secuencial respecto a ellas.
- **Pulido (F7)**: tras las historias; T023 → T024.

### Dentro de cada historia

- Pruebas (fallan, revisión del autor, commit `test`) → implementación (verde, commit `feat`).
- `app/config.py` lo editan T005, T010, T017, T019 y T022; `app/main.py`, T005, T011, T015, T017
  y T022: no paralelizar tareas que comparten archivo.

### Oportunidades de paralelismo

- F1: T002 en paralelo con T001.
- US1: T007, T008 (mismo archivo, pero bloques independientes; escribir juntos) y T009 en paralelo.
- US2: T012, T013 y T014 en paralelo (archivos distintos); luego T015 → T016 → T017.
- US4: T020 y T021 en paralelo.
- F7: T025 en paralelo con T023/T024.

## Ejemplo de paralelismo: Historia 2

```text
# Fase roja (archivos distintos):
T012 tests/unit/test_db.py
T013 tests/unit/test_health_service.py
T014 tests/integration/test_health.py
# Fase verde (secuencial por dependencia):
T015 app/db.py → T016 app/services/health.py → T017 app/routers/health.py + app/main.py
```

## Estrategia de implementación

### MVP primero (US1 + US2, ambas P1)

1. F1 y F2.
2. US1: producción ya no puede arrancar mal configurada (y `create_app(settings)` queda listo).
3. US2: health checks listos para Render y el job de despliegue.
4. **Parar y validar**: con esto ya se puede desplegar con seguridad.

### Entrega incremental

- US3 refuerza el determinismo de las pruebas; US4 cierra `/docs` y ajusta el log; F7 deja
  documentadas las variables y valida de punta a punta.
- Un commit `test` y uno `feat` por cada par prueba → implementación, siempre en
  `feature/PED-11-ambientes-despliegue`.
