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
cp .env.example .env         # ajusta los valores si hace falta
uv run pre-commit install    # instala los hooks de calidad y de mensaje de commit
uv run fastapi dev app/main.py
```

La app queda en http://127.0.0.1:8000, la documentación de la API en `/docs` y el health check en `/health`.

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

Se completa en las historias HU-03 (despliegue) y HU-12 (logs y rollback).

## Componentes reutilizados y uso de IA

- Dependencias de terceros: ver `pyproject.toml` (FastAPI, Pydantic Settings y herramientas de desarrollo: ruff, mypy, pytest, pre-commit). Cada una conserva su licencia.
- Uso de IA en el desarrollo: la estructura inicial del repositorio y la configuración de calidad se generaron con ayuda de un asistente de IA (Claude) y fueron revisadas y adaptadas antes de integrarse.
