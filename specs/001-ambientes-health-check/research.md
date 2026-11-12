# Investigación (Fase 0): PED-11 · HU-03 Ambientes y health check

Cada decisión sigue el formato Decisión / Justificación / Alternativas. No quedan puntos
«NEEDS CLARIFICATION» en el contexto técnico.

## R1. Saber el ambiente antes de decidir si se lee `.env`

- **Decisión**: `get_settings()` lee primero `ENVIRONMENT` de las variables del proceso
  (`os.environ`). Si vale `test`, construye `Settings(_env_file=None)`; en otro caso,
  `Settings()` con `env_file=".env"`. `tests/conftest.py` fija `os.environ["ENVIRONMENT"] = "test"`
  en su primera línea, antes de importar `app`.
- **Justificación**: el ambiente decide si se lee el archivo, así que no puede salir del propio
  archivo. La CI ya define `ENVIRONMENT: test` (`.github/workflows/ci.yml`), por lo que no hay que
  tocar `.github/`. `_env_file` es el argumento de inicialización documentado de pydantic-settings
  para sobrescribir `env_file` en una instancia.
- **Alternativas**: leer siempre `.env` y confiar en que el proceso gane (rechazada: una variable
  que solo existe en `.env`, como `GEMINI_API_KEY`, se colaría en las pruebas); usar una subclase
  `TestSettings` (rechazada: duplica la lógica de validación).

## R2. Valores por defecto que dependen del ambiente

- **Decisión**: `log_level`, `ai_provider`, `database_url` y `secret_key` se declaran opcionales (`None`) y un
  `model_validator(mode="after")` los completa según el ambiente; el mismo validador acumula todos
  los errores de producción en una lista y lanza un único `ValueError` con todos.
  Defaults: `environment="production"`; `log_level` DEBUG en `local`, INFO en `test` y
  `production`; `ai_provider` `fake` en `local`/`test`, `gemini` en `production`; `database_url`
  `sqlite:///./pedidofacil.db` en `local` y `sqlite://` (memoria) en `test`; `secret_key`
  `secrets.token_urlsafe(48)` en `local` y `test` (ningún valor escrito en el código, que además
  evita el aviso S105 de ruff).
- **Justificación**: un default de campo no puede depender de otro campo; el validador «after» ve
  el modelo completo y permite listar todas las variables que fallan a la vez (FR-007).
- **Alternativas**: `default_factory` que lee `os.environ` (rechazada: ignora `.env` y argumentos);
  un validador por campo (rechazada: reportaría solo el primer error).

## R3. Que los errores de configuración no filtren secretos

- **Decisión**: `SECRET_KEY`, `GEMINI_API_KEY` y `DATABASE_URL` se tipan como `SecretStr`, y el
  modelo usa `hide_input_in_errors=True`. El mensaje del `ValueError` solo nombra variables y
  motivos y, en producción, termina con «Para desarrollo local copia .env.example a .env
  (ENVIRONMENT=local)».
- **Justificación**: por defecto, el `ValidationError` de Pydantic imprime `input_value` con los
  datos de entrada; en un validador de modelo eso incluiría todas las variables (FR-007, SC-006,
  principio VI). `SecretStr` además evita que un `repr(settings)` o un log muestren los valores.
- **Alternativas**: atrapar la excepción y reescribirla (rechazada: más código y fácil de olvidar
  en otro punto de entrada).

## R4. Reconocer y conectar PostgreSQL (Neon) con psycopg 3

- **Decisión**: en producción, `DATABASE_URL` es válido si su esquema empieza por `postgresql` o
  `postgres`. `app/db.py` normaliza `postgres://` y `postgresql://` a `postgresql+psycopg://` antes
  de crear el motor, y pasa `connect_args={"connect_timeout": 5}` y `pool_pre_ping=True`.
- **Justificación**: Neon entrega URLs `postgresql://…?sslmode=require`; sin el sufijo
  `+psycopg`, SQLAlchemy intenta usar psycopg2, que no se instala. `connect_timeout` acota a 5 s la
  espera cuando la base no responde (FR-012, SC-003), y `pool_pre_ping` descarta conexiones que
  Neon cerró al suspenderse.
- **Alternativas**: exigir que el usuario escriba `postgresql+psycopg://` (rechazada: error fácil
  al copiar la URL de Neon); instalar psycopg2 (rechazada: psycopg 3 es el recomendado y ya se pidió).
- **Nota**: el `statement_timeout` por opciones de arranque no se usa porque el pooler de Neon
  (PgBouncer) no acepta parámetros de inicio; `SELECT 1` no necesita más.

## R5. SQLite en memoria compartido entre hilos en las pruebas

- **Decisión**: para URLs `sqlite`, el motor usa `connect_args={"check_same_thread": False}` y,
  si es en memoria, `poolclass=StaticPool`.
- **Justificación**: `TestClient` ejecuta los endpoints síncronos en otro hilo; sin esto, SQLite
  rechaza la conexión o cada conexión ve una base distinta.
- **Alternativas**: SQLite en archivo temporal (rechazada: más lento y deja archivos).

## R6. Fuente única de configuración y sesión inyectable

- **Decisión**: `create_app(settings: Settings | None = None)` guarda `settings` y el motor
  (`build_engine(...)`) en `app.state`. `app/db.py` expone `build_engine(url: str) -> Engine` y la
  dependencia `get_session(request)`, que abre una `Session` de SQLModel sobre
  `request.app.state.engine` y la cierra al terminar; `get_app_settings(request)` (en
  `app/config.py`) devuelve `request.app.state.settings`. El router los recibe con `Depends`.
- **Justificación**: una sola fuente evita que la configuración pasada a `create_app` y la de la
  caché de `get_settings()` diverjan; cada prueba construye su propia app con su `Settings` sin
  limpiar cachés. Es el equivalente a inyectar un `DataSource` y las `@ConfigurationProperties` en
  Spring; las pruebas reemplazan `get_session` con `app.dependency_overrides` (como un
  `@MockBean`). El motor no conecta al crearse: `/health/live` nunca abre una conexión (SC-008).
- **Alternativas**: `get_engine()` en caché a partir de `get_settings()` (rechazada: dos fuentes
  de configuración); motor global al importar el módulo (rechazada: conectaría o fallaría al
  importar y dificulta las pruebas).

## R7. Ubicación de la comprobación de la base (capas)

- **Decisión**: `app/routers/health.py` define `/health` y `/health/live`;
  `app/services/health.py` define `check_database(session) -> bool`, que ejecuta `SELECT 1` y
  devuelve `False` ante `SQLAlchemyError` (registrando el error sin credenciales).
- **Justificación**: el principio IV fija routers → services; el router no ejecuta SQL. No se crea
  repositorio: no hay tablas ni entidades (YAGNI).
- **Alternativas**: SQL en el router (rechazada: rompe las capas); un repositorio de «salud»
  (rechazada: abstracción sin uso).

## R8. Simular la caída de la base en las pruebas

- **Decisión**: en la prueba del 503, `app.dependency_overrides[get_session]` devuelve un doble
  cuya ejecución lanza `sqlalchemy.exc.OperationalError`. El caso 200 usa la sesión real sobre
  SQLite en memoria.
- **Justificación**: determinista y sin red (principio II); prueba el contrato HTTP completo.
- **Alternativas**: apuntar a un host inexistente (rechazada: lento y depende de DNS/red).

## R9. Desactivar la documentación en producción

- **Decisión**: `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` en `production`; en
  `local` y `test`, los valores por defecto.
- **Justificación**: con `openapi_url=None` también desaparece el esquema, que si no seguiría
  exponiendo todos los endpoints (FR-009).

## R10. Health checks en Render y en el job de despliegue

- **Decisión**: la ruta de health check del servicio en Render se cambia a `/health/live` (ajuste
  manual en el panel; no hay `render.yaml`). El job `deploy` de la CI ya consulta `/health` y
  compara `commit`; con el nuevo contrato sigue funcionando sin cambios (un 503 hace fallar
  `curl -f` y el job reintenta).
- **Justificación**: las comprobaciones frecuentes de la plataforma no tocan la base, que Neon puede
  suspender (spec, clarificación 3); el despliegue sí verifica la base una vez por despliegue.
- **Alternativas**: modificar `.github/workflows/ci.yml` (innecesario y requiere permiso).

## R11. Dependencias nuevas

- **Decisión**: `uv add sqlmodel "psycopg[binary]"`.
- **Justificación**: `sqlmodel` es el ORM fijado por la constitución y lo necesita `get_session`;
  `psycopg[binary]` es el controlador de PostgreSQL para producción, con binarios precompilados
  para no requerir `libpq` en Render. Ambas son necesarias en esta historia (FR-004, FR-011).
- **Alternativas**: diferir `psycopg` a HU-15 (rechazada: el health check de producción no podría
  conectarse a Neon).
