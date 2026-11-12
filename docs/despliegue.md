# Guía de despliegue y recuperación

PedidoFácil se despliega en Render con PostgreSQL en Neon. El despliegue lo dispara GitHub Actions solo cuando un cambio llega a `main` y pasa la CI, y cada despliegue queda registrado en **Deployments → production** del repositorio.

```
PR → «Calidad y pruebas» → squash merge a main
        → CI en main → job «Desplegar a producción»
              → Deploy Hook de Render → build (uv sync) → start (fastapi run)
              → verificación: /health debe reportar el commit integrado
```

## Ambientes

| Ambiente | `ENVIRONMENT` | Base de datos | IA | Dónde se configura |
|---|---|---|---|---|
| Pruebas | `test` | SQLite en memoria | Modelos falsos de Pydantic AI | `tests/conftest.py` y `ci.yml` (no lee `.env`) |
| Desarrollo | `local` | SQLite en archivo | `AI_PROVIDER=fake` por defecto | Archivo `.env` (copia de `.env.example`) |
| Producción | `production` | PostgreSQL en Neon | `AI_PROVIDER=gemini` | Variables de entorno de Render |

Cada ambiente usa sus propias credenciales. Las de producción nunca se usan en un equipo local, y el bot de Telegram de producción tiene un token distinto del de pruebas.

## Reproducir el despliegue desde cero

### 1. Base de datos (Neon)

1. Crear el proyecto `pedidofacil` en la región **AWS US East 1 (N. Virginia)**, solo con Postgres.
2. En **Connect**, con la rama `production` y **Connection pooling desactivado**, copiar la cadena de conexión.
3. Conservar `?sslmode=require&channel_binding=require`. No hace falta cambiar el prefijo: la app convierte `postgresql://` (y `postgres://`) a `postgresql+psycopg://` al crear el motor.

### 2. Servicio web (Render)

**New → Web Service**, conectado al repositorio `Juan-cely-l/PedidoFacil`:

| Campo | Valor |
|---|---|
| Region | Virginia (US East) |
| Branch | `main` |
| Runtime | Python 3 (Render detecta uv por `uv.lock` y la versión por `.python-version`) |
| Build Command | `uv sync --frozen --no-dev && uv cache prune --ci` |
| Start Command | `uv run --no-sync fastapi run app/main.py --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |
| Health Check Path | `/health/live` (no consulta la base: así Neon puede suspenderse y una caída de la base no reinicia la app) |
| Auto-Deploy | Off |

Cuando existan migraciones (Alembic), el Start Command pasa a ser `uv run --no-sync alembic upgrade head && uv run --no-sync fastapi run app/main.py --host 0.0.0.0 --port $PORT`.

Variables de entorno:

| Variable | Valor |
|---|---|
| `ENVIRONMENT` | `production` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | Cadena de Neon (`postgresql://…` o `postgresql+psycopg://…`) |
| `SECRET_KEY` | Generada con el botón **Generate** de Render |
| `AI_PROVIDER` | `fake` hasta HU-08; luego `gemini` |
| `GEMINI_API_KEY` | Solo cuando `AI_PROVIDER=gemini` |

### 3. Environment `production` (GitHub)

En **Settings → Environments → production**:

- **Deployment branches:** solo `main`.
- **Secreto** `RENDER_DEPLOY_HOOK_URL`: la URL de **Render → Settings → Deploy Hook**.
- **Variable** `PRODUCTION_URL`: la URL pública del servicio, sin `/` al final.

### 4. Job de despliegue

El job `deploy` de `.github/workflows/ci.yml` solo corre en `push` a `main` y después de `checks`. Llama al Deploy Hook y consulta `/health` cada 15 segundos (hasta 10 minutos) hasta que el campo `commit` coincide con el commit integrado. Si no coincide a tiempo, el job falla en rojo.

## Verificar un despliegue

1. **Actions:** el workflow del merge muestra «Calidad y pruebas» y «Desplegar a producción» en verde.
2. **Deployments → production:** el último despliegue apunta al commit del PR.
3. `GET <PRODUCTION_URL>/health` responde `200` con `"status": "ok"`, el estado de la base de datos y el commit desplegado.

## Recuperación (rollback)

| Situación | Acción | Efecto |
|---|---|---|
| Un despliegue rompió producción y hay que restaurar ya | Render → **Events** → **Rollback** en el último despliegue correcto | Producción vuelve a esa versión en uno o dos minutos |
| Hay que deshacer el cambio de forma permanente | `git revert <commit>` en una rama, PR y merge | El pipeline despliega `main` sin el cambio |

El rollback de Render es temporal: el siguiente merge a `main` vuelve a desplegar lo que haya en `main`. Por eso, después de un rollback de emergencia, siempre se hace el `git revert`.

Tras cualquiera de los dos, se verifica con `/health` que el commit reportado es el esperado, y se registra en el issue de Jira correspondiente.

## Problemas conocidos

| Síntoma | Causa probable | Solución |
|---|---|---|
| «Exited with status 1» al arrancar | Una variable de entorno con un valor no admitido (por ejemplo, `Production` o `info`) | Revisar los valores exactos en Render → Environment |
| La primera petición tarda unos 50 s | El plan Free de Render se suspende tras unos 15 minutos sin uso | Abrir la URL unos minutos antes de una demostración |
| El job de despliegue falla esperando `/health` | La app no arrancó o el despliegue tardó más de 10 minutos | Revisar los logs del despliegue en Render |
| `/health` responde 503 | No hay conexión con Neon | Revisar `DATABASE_URL` y el estado del proyecto en Neon |
