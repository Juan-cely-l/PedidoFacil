# PedidoFácil

Registro y seguimiento de pedidos para emprendimientos que hoy reciben pedidos por WhatsApp y los anotan a mano. El dueño pega el mensaje del cliente y la IA arma el pedido; el cliente consulta el estado con un enlace.

Proyecto final de Ingeniería de Software · Tablero en Jira: proyecto `PED`.

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (gestiona Python 3.12 y las dependencias)
- Git

## Ejecutar en local

```bash
git clone <url-del-repo> && cd pedidofacil
uv sync                      # crea .venv con las versiones exactas de uv.lock
cp .env.example .env         # obligatorio: trae ENVIRONMENT=local
uv run pre-commit install    # instala los hooks de calidad y de mensaje de commit
uv run alembic upgrade head  # crea o actualiza las tablas de la base local
uv run fastapi dev app/main.py
```

La app queda en http://127.0.0.1:8000 y la documentación de la API en `/docs`.

### Ambientes

`ENVIRONMENT` admite tres valores y, **si falta, se asume `production`**, el más estricto: sin el `.env` local la app se niega a arrancar y el error indica qué variables faltan.

| Ambiente | Para qué | Base de datos | IA | Lee `.env` | `/docs` | Log por defecto |
|---|---|---|---|---|---|---|
| `test` | Pruebas y CI | SQLite en memoria | `fake` | No | Sí | INFO |
| `local` | Desarrollo | SQLite en `./pedidofacil.db` | `fake` | Sí | Sí | DEBUG |
| `production` | Render | PostgreSQL (Neon), obligatorio | `gemini` | Sí | No | INFO |

En `production` la app no arranca si falta alguna de estas variables:
- `DATABASE_URL` de PostgreSQL;
- `SECRET_KEY`, de mínimo 32 caracteres;
- `GEMINI_API_KEY`, cuando `AI_PROVIDER=gemini`;
- las variables del login con Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_EMAILS` y `PUBLIC_BASE_URL` con `https`.

Todas las variables están explicadas en `.env.example`.

### Login con Google en local

La gestión (catálogo y lo que venga después) exige la sesión del dueño. Sin ella, cualquier ruta redirige a `/login`, salvo `/health`, `/health/live` y las rutas del propio login. El dueño entra con su cuenta de Google, y la app no guarda contraseñas.

Para probar el login real en tu equipo:

1. **Cliente OAuth:** crea uno en Google Cloud siguiendo [docs/despliegue.md](docs/despliegue.md#3-login-con-google-google-cloud). Necesitas la pantalla de consentimiento en modo Testing, tu correo como usuario de prueba y la URI `http://127.0.0.1:8000/auth/google/callback` registrada.
2. **Variables en `.env`:**

   ```bash
   GOOGLE_CLIENT_ID=<id del cliente>.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=<secreto del cliente>
   OWNER_EMAILS=tu-correo@gmail.com           # varios, separados por comas
   PUBLIC_BASE_URL=http://127.0.0.1:8000      # opcional: es el valor por defecto en local
   SECRET_KEY=<uv run python -c "import secrets; print(secrets.token_urlsafe(48))">
   ```

   Con `SECRET_KEY` fija, la sesión sobrevive a los reinicios de `fastapi dev`. Si falta, se genera una al azar en cada arranque y hay que volver a entrar.
3. **El mismo host:** abre la app en el host de `PUBLIC_BASE_URL`, es decir, http://127.0.0.1:8000 y no `localhost:8000`. La cookie de sesión es de un host, y Google vuelve al host de `PUBLIC_BASE_URL`. Si son distintos, el login termina en «No se completó el inicio de sesión con Google». Para usar `localhost`, pon `PUBLIC_BASE_URL=http://localhost:8000` y registra también esa URI.

Sin las variables de Google, la app arranca igual en local, pero «Entrar con Google» muestra un aviso de error.

**Las pruebas no necesitan credenciales.** Usan un proveedor de identidad simulado y un Google falso en memoria, y nunca llaman a Google ni leen el `.env`.

### Health checks

| Ruta | Consulta la base | Respuesta | Lo usa |
|---|---|---|---|
| `GET /health/live` | No | `200` con `status`, `version` y `commit` | Render (Health Check Path) |
| `GET /health` | Sí (`SELECT 1`) | `200`, o `503` si la base no responde, con `status`, `database`, `version` y `commit` | El job de despliegue de la CI |

## Comandos de calidad

| Qué | Comando |
|---|---|
| Pruebas con cobertura | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Formato | `uv run ruff format .` |
| Tipos | `uv run mypy` |
| Todos los hooks sobre todo el repo | `uv run pre-commit run --all-files` |
| Agregar una dependencia | `uv add <paquete>` (o `uv add --dev <paquete>`) |

La CI (`.github/workflows/ci.yml`) ejecuta lint, formato, tipos y pruebas en cada push a `main` y en cada pull request. La cobertura mínima es del 80 %.

## Flujo de trabajo

1. Cada cambio nace de un issue de Jira (`PED-XX`).
2. Rama: `feature/PED-XX-descripcion-corta` (o `fix/…`, `docs/…`). Los commits directos a `main` están bloqueados por un hook y por las reglas de GitHub.
3. Commits con el formato `tipo(PED-XX): descripción`, por ejemplo `feat(PED-12): registrar pedido manual`. El hook `commit-msg` lo valida.
4. Pull request con la plantilla (checklist de la Definición de Terminado). Solo se integra con la CI en verde, usando *squash merge*.
5. Al cerrar cada sprint se etiqueta la versión: `v0.1`, `v0.2`, `v1.0`.

## Despliegue y recuperación

Ver [docs/despliegue.md](docs/despliegue.md). Los logs y el rollback se completan en HU-12.

## Componentes reutilizados y uso de IA

- Dependencias de terceros: ver `pyproject.toml` (FastAPI, Pydantic Settings, SQLModel, psycopg, Authlib e itsdangerous para el login con Google, y herramientas de desarrollo: ruff, mypy, pytest, time-machine, pre-commit). Cada una conserva su licencia.
- Uso de IA en el desarrollo: la estructura inicial del repositorio y la configuración de calidad se generaron con ayuda de un asistente de IA (Claude) y fueron revisadas y adaptadas antes de integrarse.
