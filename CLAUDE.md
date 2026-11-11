# PedidoFácil: instrucciones para Claude Code

La constitución (`.specify/memory/constitution.md`) prevalece sobre este archivo.

## Contexto
- App que convierte el mensaje de un cliente en una cotización con precios e inventario reales, la envía por WhatsApp o Telegram y la convierte en pedido; incluye un bot de Telegram que atiende solo y alertas de stock bajo.
- Proyecto académico individual, gestionado en Jira (proyecto `PED`). Entrega: 29 de noviembre de 2026.
- El autor viene de Spring Boot: al explicar código, relaciónalo con su equivalente en Spring cuando ayude (Depends ↔ inyección de dependencias, Pydantic ↔ DTO + Bean Validation, Alembic ↔ Flyway, TestClient ↔ MockMvc).

## Comandos
- Dependencias: `uv sync` · agregar: `uv add <paquete>` o `uv add --dev <paquete>` (nunca pip)
- Pruebas: `uv run pytest`
- Calidad: `uv run ruff check . && uv run ruff format . && uv run mypy`
- Migraciones: `uv run alembic revision --autogenerate -m "..."` · `uv run alembic upgrade head`
- App local: `uv run fastapi dev app/main.py`

## Stack y arquitectura
- FastAPI en capas: `app/routers/` → `app/services/` → `app/repositories/`; modelos en `app/models/`; plantillas en `app/templates/`.
- SQLModel + Alembic (nunca `create_all` fuera de las pruebas). SQLite en local y pruebas; PostgreSQL (Neon) en producción vía `DATABASE_URL`.
- Interfaz: Jinja2 + HTMX + Pico.css. Sin frameworks de frontend.
- IA: Pydantic AI con Gemini. En pruebas: `TestModel`/`FunctionModel` y `ALLOW_MODEL_REQUESTS=False`.
- Telegram: Bot API con httpx y webhook en `app/routers/telegram.py`; en pruebas, `httpx.MockTransport`.
- Envío desde la web: enlaces `wa.me` y `t.me/share`, sin API de WhatsApp.
- Montos: enteros en pesos (nunca float); descuento de inventario dentro de una transacción.
- Login: SessionMiddleware de Starlette + `pwdlib[argon2]`; un solo usuario (el dueño).
- Pruebas: `tests/unit` (servicios, sin HTTP) y `tests/integration` (endpoints con `TestClient`); fechas congeladas con `time-machine`.

## Commits (automáticos, siguiendo TDD)
- Toma la clave de Jira del nombre de la rama (`feature/PED-12-...` → `PED-12`); nunca trabajes ni hagas commits en `main`.
- Haz commit en cada fase del ciclo TDD, con el formato `tipo(PED-XX): descripción` en español:
  1. Rojo: después de que yo apruebe la prueba que falla → `test(PED-XX): ...`
  2. Verde: cuando `uv run pytest` pase completo → `feat(PED-XX): ...` o `fix(PED-XX): ...`
  3. Refactor (si hubo): con todo en verde → `refactor(PED-XX): ...`
- Antes de los commits verde y refactor, ejecuta `uv run pytest`, `uv run ruff check .` y `uv run mypy`; si algo falla, corrige primero.
- Si un hook de pre-commit modifica archivos o falla, corrige, vuelve a hacer `git add` y repite el commit. Nunca uses `--no-verify`.
- Mantén la línea `Co-Authored-By` que agregas por defecto (declara el uso de IA).
- No hagas push ni abras PR sin que te lo pida.


## Reglas de trabajo
- TDD estricto: escribe la prueba, ejecútala y muéstrame que falla por la razón esperada; luego escribe el código mínimo para que pase; luego refactoriza con todo en verde.
- Detente después de la fase roja de cada tarea para que revise la prueba antes de implementar.
- Nunca llames a la API real de Gemini ni a ningún servicio externo en las pruebas.
- Agrega dependencias solo cuando la historia actual las necesite.
- No modifiques `.github/`, `.pre-commit-config.yaml`, la configuración de herramientas en `pyproject.toml` ni la constitución sin pedírmelo.
- Interfaz, docstrings, mensajes y nombres de pruebas en español; identificadores de código en inglés.
- La IA nunca calcula precios ni totales; si una prueba o un plan lo propone, detente y avísame.
