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

En `production` la app no arranca si falta `DATABASE_URL` de PostgreSQL, `SECRET_KEY` (mínimo 32 caracteres) o, con `AI_PROVIDER=gemini`, `GEMINI_API_KEY`. Todas las variables están explicadas en `.env.example`.

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

- Dependencias de terceros: ver `pyproject.toml` (FastAPI, Pydantic Settings, SQLModel, psycopg y herramientas de desarrollo: ruff, mypy, pytest, pre-commit). Cada una conserva su licencia.
- Uso de IA en el desarrollo: la estructura inicial del repositorio y la configuración de calidad se generaron con ayuda de un asistente de IA (Claude) y fueron revisadas y adaptadas antes de integrarse.
