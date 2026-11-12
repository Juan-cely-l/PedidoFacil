# Guía de validación: PED-11 · HU-03 Ambientes y health check

## Requisitos previos

- `uv sync` con las dependencias nuevas (`sqlmodel`, `psycopg[binary]`).
- Para la parte de producción: una URL de Neon y una `SECRET_KEY` de al menos 32 caracteres.

## 1. Pruebas automáticas

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Esperado: todo en verde y cobertura ≥ 80 %. Repetir `uv run pytest` con y sin un `.env` local: el
resultado debe ser idéntico (SC-005).

## 2. Ambiente local

```bash
cp .env.example .env            # trae ENVIRONMENT=local
uv run fastapi dev app/main.py
```

- `GET http://127.0.0.1:8000/health/live` → 200, `commit: "local"`.
- `GET http://127.0.0.1:8000/health` → 200, `database: "ok"` (SQLite local).
- `GET http://127.0.0.1:8000/docs` → página de documentación.
- El log muestra mensajes DEBUG.

## 3. Producción mal configurada (sin red)

```bash
env -i PATH="$PATH" HOME="$HOME" uv run --no-env-file python -c "import app.main"
```

Esperado: falla nombrando `DATABASE_URL`, `SECRET_KEY` y `GEMINI_API_KEY`, sin valores, y con la
sugerencia «Para desarrollo local copia .env.example a .env (ENVIRONMENT=local)». Ejecutarlo desde
un directorio sin `.env` o renombrándolo antes, ya que fuera de `test` se lee `.env`.

Variantes: `DATABASE_URL=sqlite:///x.db` → error de PostgreSQL; `SECRET_KEY` de 31 caracteres →
error de longitud; `AI_PROVIDER=fake` con el resto válido → arranca con un WARNING.

## 4. Producción en Render

1. Variables del servicio: `ENVIRONMENT=production`, `DATABASE_URL` (Neon), `SECRET_KEY`,
   `GEMINI_API_KEY` (o `AI_PROVIDER=fake`).
2. Settings → Health Check Path: `/health/live`.
3. Tras integrar en `main`, el job «Desplegar a producción» consulta `/health` hasta ver el commit.
4. Comprobar `GET <URL>/docs` → 404 y `GET <URL>/health` → 200 con `database: "ok"`.

Contratos: [contracts/health.md](contracts/health.md) ·
[contracts/configuration.md](contracts/configuration.md).
