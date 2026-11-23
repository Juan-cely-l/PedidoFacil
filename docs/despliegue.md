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

Desde PED-88 hay migraciones (Alembic, en `migrations/`) y el Start Command pasa a ser
`uv run --no-sync alembic upgrade head && uv run --no-sync fastapi run app/main.py --host 0.0.0.0 --port $PORT`. El cambio se hace **después** de integrar el PR que trae las migraciones, nunca antes:
mientras `main` no tenga `alembic` ni `migrations/`, ese comando falla y la app no arranca.

Orden del primer despliegue con migraciones:

1. Integrar el PR en `main`. La CI despliega con el Start Command anterior: la app arranca y
   `/health` responde, pero `/productos` da error 500 porque la tabla `product` aún no existe.
2. En Render → Settings, cambiar el Start Command al de arriba y lanzar **Manual Deploy →
   Deploy latest commit**. Al arrancar, `alembic upgrade head` crea las tablas en Neon.
3. Verificar `/health` (commit esperado) y que `/productos` responda 200. Desde PED-15, esa
   verificación se hace con la sesión iniciada; sin ella, `/productos` redirige a `/login`.

A partir de ahí, cada despliegue aplica las migraciones pendientes antes de arrancar la app.

Variables de entorno:

| Variable | Valor |
|---|---|
| `ENVIRONMENT` | `production` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | Cadena de Neon (`postgresql://…` o `postgresql+psycopg://…`) |
| `SECRET_KEY` | Generada con el botón **Generate** de Render |
| `AI_PROVIDER` | `gemini` desde HU-08 (PED-16) |
| `GEMINI_API_KEY` | Clave de Google AI Studio; obligatoria con `AI_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` (el valor por defecto; elegido por medición) |
| `GEMINI_FALLBACK_MODEL` | `ninguno`: el único respaldo de otra familia, `gemini-3.8-flash`, quedó descartado por cuota |
| `AI_TIMEOUT_SECONDS` | `10` (el valor por defecto); la app no acepta más de 15 s |
| `GOOGLE_CLIENT_ID` | ID del cliente OAuth de Google (sección 3) |
| `GOOGLE_CLIENT_SECRET` | Secreto del mismo cliente OAuth |
| `OWNER_EMAILS` | Correos autorizados a entrar, separados por comas (por ejemplo, el Gmail del dueño) |
| `PUBLIC_BASE_URL` | `https://pedidofacil-6nky.onrender.com` (sin `/` al final; debe ser `https`) |

Desde PED-15 (HU-07), la app **no arranca en producción** si falta alguna de las cuatro
variables de Google, si `OWNER_EMAILS` queda vacía o si `PUBLIC_BASE_URL` no usa `https`. Si
`PUBLIC_BASE_URL` falta, se usa `RENDER_EXTERNAL_URL`, que Render define solo. Igual conviene
fijarla, porque determina la URI de vuelta registrada en Google. Esas variables se definen en
Render **antes** de integrar el PR: si no, el despliegue falla al arrancar.

Desde PED-16 (HU-08), con `AI_PROVIDER=gemini` la app **no arranca** sin `GEMINI_API_KEY`, ni con
un `AI_TIMEOUT_SECONDS` mayor que 15 o un `GEMINI_FALLBACK_MODEL` igual a `GEMINI_MODEL`. Las
variables de la IA también se definen **antes** de integrar el PR.

**Volver a medir los modelos**: si el proveedor cambia o la latencia empeora, se repite la
medición con `scripts/medir_gemini.py`, con el protocolo de
[research R2](../specs/004-cotizacion-con-ia/research.md#cómo-se-vuelve-a-medir-antes-del-merge-y-cada-vez-que-se-dude).
El resultado solo cambia `GEMINI_MODEL` o `GEMINI_FALLBACK_MODEL` en Render, sin tocar el código.

### 3. Login con Google (Google Cloud)

El dueño entra con su cuenta de Google (OAuth 2.0 / OpenID Connect, ADR 0003). La app no guarda
contraseñas, y solo entran los correos de `OWNER_EMAILS`: autenticarse con Google no basta.

En [Google Cloud Console](https://console.cloud.google.com/):

1. **Proyecto:** crear uno, por ejemplo `pedidofacil`.
2. **Pantalla de consentimiento de OAuth** (APIs y servicios → Pantalla de consentimiento):
   - tipo de usuario **Externo**;
   - estado de publicación **Testing**, sin publicarla: así no hace falta la verificación de
     Google y solo pueden autenticarse los usuarios de prueba;
   - alcances: `openid`, `email` y `profile`, que no requieren revisión.
3. **Usuarios de prueba:** agregar el correo del dueño. En modo Testing, Google rechaza a
   cualquier cuenta que no esté en esa lista, antes de llegar a la app. Esto es una barrera
   adicional, no reemplaza a `OWNER_EMAILS`. El correo debe estar en las dos listas.
4. **Credenciales** → Crear credenciales → **ID de cliente de OAuth**, tipo **Aplicación web**.
   En **URIs de redireccionamiento autorizados**, registrar las tres:

   | Ambiente | URI |
   |---|---|
   | Local | `http://127.0.0.1:8000/auth/google/callback` |
   | Local (alternativa) | `http://localhost:8000/auth/google/callback` |
   | Producción | `https://pedidofacil-6nky.onrender.com/auth/google/callback` |

   No hace falta un **origen de JavaScript autorizado**: el flujo ocurre solo en el servidor.
5. Copiar el **ID de cliente** y el **secreto** a `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en
   Render. Lo ideal es usar un cliente OAuth distinto para local, o al menos no copiar el
   secreto a equipos que no sean del dueño.

La URI de vuelta que la app envía a Google es `PUBLIC_BASE_URL` + `/auth/google/callback`. Tiene
que coincidir carácter por carácter con una de las registradas. Si no, Google muestra
`redirect_uri_mismatch`.

Qué queda público: `/health`, `/health/live` (Render los usa como health check), `/login`,
`/login/google` y `/auth/google/callback`. Todo lo demás, incluido `/productos`, exige sesión y
sin ella redirige a `/login`. En producción no existen `/docs` ni `/openapi.json`.

La sesión vive en una cookie firmada con `SECRET_KEY`, de tipo `HttpOnly`, `SameSite=lax` y
`Secure`. Sobrevive a un reinicio o redeploy de la app y caduca 12 horas después del login, aunque
se use sin parar. Para salir antes, está el botón «Cerrar sesión».

### 4. Rotar `SECRET_KEY`

Cambiar `SECRET_KEY` invalida la firma de todas las cookies de sesión:

- **Todas las sesiones se cierran a la vez**: el dueño tiene que volver a entrar con Google.
- **Los logins a medio camino fallan**: el `state` de OAuth vive en la sesión vieja. El dueño ve
  «No se completó el inicio de sesión con Google» y reintenta.
- **No se pierde nada más**: ningún dato persistente está cifrado con esa clave.

**Cuándo rotarla:** ante sospecha de filtración de la clave o de robo de una cookie de sesión. Es
la única forma de cerrar todas las sesiones a la vez. Para cortar solo el acceso de un correo,
basta con quitarlo de `OWNER_EMAILS` y redesplegar: la app vuelve a comprobar la lista en cada
petición.

**Cómo:** Render → Environment → `SECRET_KEY` → **Generate** → guardar, y después **Manual Deploy**
si Render no redespliega solo.

### 5. Environment `production` (GitHub)

En **Settings → Environments → production**:

- **Deployment branches:** solo `main`.
- **Secreto** `RENDER_DEPLOY_HOOK_URL`: la URL de **Render → Settings → Deploy Hook**.
- **Variable** `PRODUCTION_URL`: la URL pública del servicio, sin `/` al final.

### 6. Job de despliegue

El job `deploy` de `.github/workflows/ci.yml` solo corre en `push` a `main` y después de `checks`. Llama al Deploy Hook y consulta `/health` cada 15 segundos (hasta 10 minutos) hasta que el campo `commit` coincide con el commit integrado. Si no coincide a tiempo, el job falla en rojo.

## Verificar un despliegue

1. **Actions:** el workflow del merge muestra «Calidad y pruebas» y «Desplegar a producción» en verde.
2. **Deployments → production:** el último despliegue apunta al commit del PR.
3. `GET <PRODUCTION_URL>/health` responde `200` con `"status": "ok"`, el estado de la base de datos y el commit desplegado.
4. En una ventana privada, `<PRODUCTION_URL>/productos` redirige a `/login`. Al entrar con el correo del dueño se ve el catálogo. Con una cuenta de Google que no está en `OWNER_EMAILS` se ve el rechazo, sin sesión.

## Recuperación (rollback)

| Situación | Acción | Efecto |
|---|---|---|
| Un despliegue rompió producción y hay que restaurar ya | Render → **Events** → **Rollback** en el último despliegue correcto | Producción vuelve a esa versión en uno o dos minutos |
| Hay que deshacer el cambio de forma permanente | `git revert <commit>` en una rama, PR y merge | El pipeline despliega `main` sin el cambio |

El rollback de Render es temporal: el siguiente merge a `main` vuelve a desplegar lo que haya en `main`. Por eso, después de un rollback de emergencia, siempre se hace el `git revert`.

Tras cualquiera de los dos, se verifica con `/health` que el commit reportado es el esperado, y se registra en el issue de Jira correspondiente.

## Riesgos aceptados

| Fecha | Riesgo | Decisión | Estado |
|---|---|---|---|
| 2026-11-16 | `/productos` (PED-88, HU-15) queda público y sin login en producción hasta HU-07 (PED-15, Sprint 3): cualquiera con la URL podría crear productos. | Aceptado por el dueño del producto: los precios no son datos sensibles. **Límite explícito**: HU-04 no se despliega a producción sin login (HU-07), porque guarda nombre, teléfono y dirección de clientes. | **Cerrado** con el despliegue de PED-15 (HU-07). Desde ese despliegue, toda ruta de gestión, incluido `/productos`, exige la sesión del dueño (denegar por defecto, verificado por `tests/integration/test_route_protection.py`). El límite de HU-04 queda **levantado**: HU-04 puede desplegarse, porque sus rutas nacen protegidas. |
| 2026-11-23 | El proveedor de IA está lento o caído: el 22 y el 23 de noviembre, con congestión dos días seguidos, del 12 % al 29 % de las consultas a `gemini-3.5-flash-lite` no obtuvieron respuesta válida en 10 s (research R2). | Aceptado: **el camino manual es parte del funcionamiento normal**, no una excepción. Toda falla de la IA termina en un borrador con el mensaje guardado y un aviso, y el dueño agrega los productos del catálogo a mano (HU-08, historia 3). La cuota gratuita también limita el volumen: con N peticiones diarias, caben N/2 cotizaciones al día. | Abierto: la demanda real se pide a la dueña en la validación (PED-70). |

## Problemas conocidos

| Síntoma | Causa probable | Solución |
|---|---|---|
| «Exited with status 1» al arrancar | Una variable de entorno con un valor no admitido (por ejemplo, `Production` o `info`) | Revisar los valores exactos en Render → Environment |
| La primera petición tarda unos 50 s | El plan Free de Render se suspende tras unos 15 minutos sin uso | Abrir la URL unos minutos antes de una demostración |
| El job de despliegue falla esperando `/health` | La app no arrancó o el despliegue tardó más de 10 minutos | Revisar los logs del despliegue en Render |
| `/health` responde 503 | No hay conexión con Neon | Revisar `DATABASE_URL` y el estado del proyecto en Neon |
| `/productos` responde 500 y `/health` 200 | Las migraciones no se aplicaron (Start Command sin `alembic upgrade head`) | Corregir el Start Command y volver a desplegar |
| «Exited with status 1» tras integrar PED-15 | Faltan `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_EMAILS` o `PUBLIC_BASE_URL`, o esta no es `https` | Definirlas en Render → Environment; el log de arranque dice cuál falta |
| Google muestra `redirect_uri_mismatch` | `PUBLIC_BASE_URL` + `/auth/google/callback` no coincide con una URI registrada | Registrar la URI exacta en Google Cloud (sección 3) o corregir `PUBLIC_BASE_URL` |
| Google dice que la app no está verificada o bloquea el acceso | La cuenta no está entre los usuarios de prueba de la pantalla de consentimiento | Agregarla en Google Cloud → Pantalla de consentimiento → Usuarios de prueba |
| «Esta cuenta de Google no tiene acceso» | El correo no está en `OWNER_EMAILS` | Agregarlo a la variable y redesplegar |
| «La IA no está disponible en este momento» o «no respondió a tiempo» | El proveedor está congestionado (503) o se agotó la cuota diaria (429) | Es el camino manual: agregar los productos a mano. El log `pedidofacil.quotes` dice el tipo de falla |
| «Exited with status 1» tras integrar PED-16 | `AI_PROVIDER=gemini` sin `GEMINI_API_KEY`, o `AI_TIMEOUT_SECONDS` mayor que 15 | Definirla en Render → Environment |
| «No se completó el inicio de sesión con Google» al volver | Se rotó `SECRET_KEY` o se reinició el login en otra pestaña | Volver a pulsar «Entrar con Google» |
