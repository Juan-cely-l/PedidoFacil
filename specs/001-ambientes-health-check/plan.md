# Plan de implementación: PED-11 · HU-03 Ambientes y health check

**Rama**: `feature/PED-11-ambientes-despliegue` | **Fecha**: 2026-11-12 | **Spec**: [spec.md](spec.md)

**Entrada**: especificación de `specs/001-ambientes-health-check/spec.md`

## Resumen

Separar los ambientes `test`, `local` y `production` con validación estricta al arrancar en
producción, y ofrecer dos health checks: `/health/live` (sin base, para Render) y `/health`
(`SELECT 1`, para el job de despliegue). Enfoque: `Settings` de pydantic-settings con un
`model_validator` que completa los defaults por ambiente y acumula los errores sin mostrar
secretos; `create_app(settings)` guarda la configuración y el motor de SQLModel en `app.state`
(fuente única); `app/db.py` con `build_engine` y la dependencia `get_session`; un servicio
`check_database` que el router consume vía `Depends`. Sin tablas ni
Alembic (HU-15). Detalle de decisiones en [research.md](research.md).

## Contexto técnico

**Lenguaje/versión**: Python 3.12 (uv)

**Dependencias principales**: FastAPI, pydantic-settings (existentes); **nuevas**: `sqlmodel`,
`psycopg[binary]` (R11)

**Almacenamiento**: SQLite (`local`: archivo; `test`: memoria) y PostgreSQL en Neon (`production`)
vía `DATABASE_URL`; sin tablas en esta historia

**Pruebas**: pytest + `TestClient`; `tests/unit` (configuración, servicio) y `tests/integration`
(endpoints); `app.dependency_overrides` para simular la caída de la base

**Plataforma**: servicio web en Render (runtime nativo de Python + uv)

**Tipo de proyecto**: servicio web (monolito FastAPI en capas)

**Metas de rendimiento**: `/health` < 5 s incluso con la base caída (`connect_timeout=5`);
`/health/live` sin E/S

**Restricciones**: sin red en pruebas; ningún secreto en errores, respuestas ni logs; cobertura
≥ 80 % con ramas; `mypy --strict`

**Escala/alcance**: 1 usuario, 1 instancia; ~6 archivos de código y ~4 de pruebas

## Verificación de la constitución

*Puerta: antes de la Fase 0 y de nuevo tras la Fase 1.*

| Principio | Cumplimiento | Estado |
|---|---|---|
| I. TDD | Cada tarea de implementación irá precedida de su prueba en `tasks.md`; commits `test` → `feat` → `refactor` | ✅ |
| II. Pruebas deterministas | `ENVIRONMENT=test` en `conftest.py` y en la CI; `_env_file=None`; SQLite en memoria; caída simulada con `dependency_overrides`, sin red (R1, R5, R8) | ✅ |
| III. Calidad | ruff, `mypy --strict` (plugin de Pydantic ya activo) y cobertura ≥ 80 % sin cambios en la configuración | ✅ |
| IV. Stack y YAGNI | SQLModel según el stack; dependencias nuevas justificadas (R11); router → service, sin repositorio porque no hay entidades (R7); sin `create_all` ni Alembic | ✅ |
| V. IA asiste | Solo se declara `AI_PROVIDER`; no hay lógica de IA | ✅ (no aplica) |
| VI. Seguridad y privacidad | `SecretStr` + `hide_input_in_errors`; respuestas 503 sin detalles; `/docs` y `/openapi.json` apagados en producción; `.env.example` sin valores (R3, R9) | ✅ |
| VII. Trazabilidad | Rama `feature/PED-11-…`; commits `tipo(PED-11): …` | ✅ |

**Tras el diseño (Fase 1)**: sin cambios; ninguna violación. La tabla de complejidad queda vacía.

## Estructura del proyecto

### Documentación (esta funcionalidad)

```text
specs/001-ambientes-health-check/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── health.md
│   └── configuration.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Código fuente

```text
app/
├── __init__.py          # MODIFICAR: __version__ + constante APP_NAME
├── config.py            # MODIFICAR: Settings por ambiente, validador, get_settings(), get_app_settings()
├── db.py                # NUEVO: build_engine(), get_session(request)
├── main.py              # MODIFICAR: create_app(settings) → app.state; docs según ambiente; log; routers
├── routers/
│   ├── __init__.py
│   └── health.py        # NUEVO: GET /health/live y GET /health
└── services/
    ├── __init__.py
    └── health.py        # NUEVO: check_database(session) -> bool

tests/
├── conftest.py          # NUEVO: ENVIRONMENT=test antes de importar app; fixtures de cliente
├── unit/
│   ├── test_config.py   # NUEVO: defaults, validaciones de producción, .env ignorado en test
│   └── test_health_service.py  # NUEVO: SELECT 1 ok / SQLAlchemyError → False
└── integration/
    ├── test_health.py   # MOVER desde tests/test_health.py y ampliar: 200/503, live, commit
    └── test_docs.py     # NUEVO: /docs 200 en local/test, 404 en producción

.env.example             # MODIFICAR: todas las variables documentadas (FR-016)
```

**Decisión de estructura**: monolito en capas existente (`app/routers` → `app/services`), y
pruebas en `tests/unit` y `tests/integration` como fija la constitución; la prueba de humo actual
se mueve a `tests/integration`.

## Notas para `/speckit-tasks`

- Fuente única: `create_app(settings: Settings | None = None)` guarda `settings` y el motor en
  `app.state`; `get_session` y el router de health los leen de `request.app.state` con `Depends`.
  Las pruebas construyen su propia app con `create_app(settings)` y no dependen de la caché de
  `get_settings()`. `app = create_app()` al importar sigue existiendo para `fastapi dev` y Render.
- `app_name` deja de ser configurable: constante `APP_NAME` en `app/__init__.py`.
- Las pruebas de configuración usan `monkeypatch.setenv`/`delenv` y `Settings(_env_file=None)` o
  un `.env` temporal en `tmp_path` (para probar que en `local` sí se lee y en `test` no).
- Solo las pruebas de `get_settings()` mismo (US3) limpian su caché (`cache_clear()`).
- Comportamiento que cambia: con `production` por defecto, `uv run fastapi dev app/main.py` sin
  `.env` deja de arrancar (es lo esperado; README y quickstart deben decirlo).

## Riesgos y pasos manuales

- **`.env.example` y `LOG_LEVEL`**: hoy trae `LOG_LEVEL=INFO` sin comentar; quien lo copie a `.env`
  anularía el DEBUG por defecto de `local` (FR-010). Al documentarlo, dejar `LOG_LEVEL` comentado.
  (La regla `deny` de `.claude/settings.json` ya se acotó a `.env`, `.env.local` y
  `.env.production`, así que `.env.example` es editable.)
- **Render**: cambiar la ruta del health check a `/health/live` y definir las variables de
  producción antes de integrar en `main`; si no, el primer despliegue falla al arrancar (por
  diseño).
- **Neon**: usar la cadena de conexión con `sslmode=require`; la primera conexión tras la
  suspensión puede tardar, cubierta por `connect_timeout=5` y los reintentos del job de despliegue.

## Seguimiento de complejidad

Sin violaciones que justificar.
