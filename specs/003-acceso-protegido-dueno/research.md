# Investigación: PED-15 · HU-07 Acceso protegido del dueño

Decisiones técnicas del plan. Las de seguridad (R1–R6) siguen el diseño pedido por el autor el
2026-11-18. Ninguna queda pendiente de aclarar.

## R1. Denegar por defecto: `require_owner` en la app entera, con `PUBLIC_PATHS` explícita

- **Decisión**:
  - `require_owner` se declara como dependencia **de la aplicación** (`FastAPI(dependencies=
    [Depends(require_owner)])`). FastAPI la aplica a todas las rutas de todos los routers
    incluidos, presentes y futuros.
  - La dependencia deja pasar sin sesión solo si `request.url.path` está en
    `PUBLIC_PATHS = {"/health", "/health/live", "/login", "/login/google",
    "/auth/google/callback"}` (comparación exacta; ninguna ruta pública lleva parámetros).
  - Sin sesión válida lanza `LoginRequired`, y un manejador de excepciones responde
    `303 See Other` a `/login`, con `?next=` en las peticiones `GET` (R4).
- **Por qué en la app y no en cada router**: pediste aplicarla «a nivel de router» y que una ruta
  nueva quede protegida sin hacer nada. Si la dependencia va en un `APIRouter`, solo cubre ese
  router: un router nuevo nacería desprotegido. Declararla en la app es la forma de cumplir lo
  segundo, y la lista pública sigue siendo explícita y única.
- **Límite conocido**: las dependencias de FastAPI solo se aplican a rutas `APIRoute`. Las rutas
  de Starlette (`app.add_route`, `app.mount`, `StaticFiles`) y las de la documentación automática
  quedan fuera. Para la documentación ver R13; para las demás, R2 las convierte en una falla de
  prueba.
- **Alternativas**:
  - Un middleware de autenticación: protege también las rutas de Starlette, pero corre antes del
    enrutamiento, no se sustituye con `dependency_overrides` y es más difícil de probar.
  - `Depends` ruta por ruta: es fácil olvidarla.

## R2. Prueba de cobertura de rutas

- **Decisión**: una sola prueba recorre `app.routes` de la app **configurada como producción**
  (`create_app(production_settings)`), donde no existe la documentación automática (R13). Así la
  prueba no necesita ninguna excepción.
  - **Rutas `APIRoute`**: para cada método de cada ruta cuyo path no esté en `PUBLIC_PATHS`, hace
    la petición sin sesión (los parámetros de path se reemplazan por `1`) y exige `303` con
    `Location` que empiece por `/login`.
  - **Rutas públicas**: verifica que no redirigen al login.
  - **Otras rutas**: cualquier ruta que no sea `APIRoute` hace fallar la prueba, sin excepciones.
  - **Sin red**: crear el motor de PostgreSQL con la URL ficticia no conecta, y las rutas
    protegidas redirigen antes de tocar la base. Para las públicas, la prueba sustituye
    `get_session` (con `FailingSession`, como en PED-11) y `get_identity_provider` (con el
    proveedor falso) mediante `dependency_overrides`. Así `/health` y `/login/google` responden
    sin intentar conectarse a nada.
- **Cuándo falla**:
  - si alguien agrega una ruta a `PUBLIC_PATHS` sin agregarla también a la lista esperada de la
    prueba;
  - si alguien monta una ruta fuera del mecanismo de dependencias;
  - si alguien quita la dependencia global.

  La lista esperada vive en la prueba, duplicada a propósito, para que ampliar lo público exija
  tocar dos sitios.

## R3. Proveedor de identidad detrás de una interfaz sustituible

- **Decisión**:
  - **Interfaz**: el protocolo `IdentityProvider` (en `app/services/identity.py`) tiene dos
    métodos:
    - `start_login(request, redirect_uri) -> Response`
    - `complete_login(request) -> VerifiedIdentity`, que lanza `LoginFailed(reason)`.
  - **Implementación real**: `GoogleIdentityProvider` usa `authlib`
    (`authlib.integrations.starlette_client.OAuth`) con
    `server_metadata_url=https://accounts.google.com/.well-known/openid-configuration` y
    `scope="openid email profile"`.
  - **Instancia**: el router la obtiene con `Depends(get_identity_provider)`, que la lee de
    `app.state`, donde la crea `create_app`.
  - **En pruebas**: `app.dependency_overrides[get_identity_provider] = lambda: FakeIdentityProvider(...)`.
    Ninguna prueba llama a Google (constitución, II).
- **Justificación**: en Spring equivale a una interfaz `IdentityProvider` con un `@Bean` real y
  otro de prueba. Aísla `authlib` en un solo módulo.

## R4. Validación del destino de retorno (`next`)

- **Decisión**: `safe_next_path(raw: str | None) -> str | None` en `app/services/auth.py`. Acepta
  solo un path relativo de la propia app:
  - debe empezar por `/`;
  - no debe empezar por `//` (el navegador lo trata como URL absoluta, `//evil.com`);
  - no debe empezar por `/\` ni contener `\` (los navegadores convierten `\` en `/`, así que
    `/\evil.com` también es absoluta);
  - `urlsplit` no debe dar ni esquema ni host;
  - no debe tener caracteres de control;
  - no debe apuntar a `/login`, `/login/google`, `/auth/google/callback` ni `/logout`.

  Cualquier otro valor da `None` y, al entrar, se va a `/productos`. El `next` se valida al
  recibirlo, se guarda en la sesión durante el viaje a Google y se vuelve a validar al usarlo.
- **Solo en `GET`**: sin sesión, un `POST` redirige al login sin `next`, porque no se puede
  repetir un envío de formulario con un redirect.

## R5. Sesión: Starlette `SessionMiddleware`, limpieza al entrar y al salir

- **Decisión**:
  - **Configuración del middleware**:
    - `secret_key=SECRET_KEY`;
    - `session_cookie="pedidofacil_session"`;
    - `max_age=SESSION_MAX_AGE_SECONDS` (12 h);
    - `same_site="lax"`;
    - `https_only=(environment == "production")`.

    Starlette marca siempre la cookie como `HttpOnly`. Igual se prueba en la cabecera
    `Set-Cookie`, para no darlo por hecho.
  - **Contenido de la sesión**: `{"owner": {"email", "name", "login_at"}}`. Nunca tokens ni
    `id_token` (constitución VI).
  - **Al entrar**: `start_session` llama a `session.clear()` y solo después escribe `owner`. Así no
    sobrevive nada de antes del login, ni datos de un tercero (fijación de sesión) ni el estado
    temporal de OAuth. El `next` se lee antes de limpiar.
  - **Al salir** (`POST /logout`, desde un formulario): `session.clear()`. Con la sesión vacía,
    Starlette envía la cookie vencida. No basta con borrar la cookie: hay que vaciar los datos.
  - **Por qué `POST` y no `GET`**: con `SameSite=lax`, el navegador sí envía la cookie en una
    navegación `GET` de nivel superior que viene de otro sitio. Un enlace, un redireccionamiento
    o una etiqueta `<img src=".../logout">` en otra página podrían cerrar la sesión del dueño sin
    que lo sepa (CSRF de cierre de sesión). Un `POST` iniciado desde otro sitio no lleva la cookie
    con `lax`. Por eso `/logout` solo existe para `POST`: un `GET /logout` responde `405` y la
    sesión sigue intacta, cosa que se prueba.
  - **Caducidad absoluta**: Starlette reenvía la cookie con `max_age` en cada respuesta, así que
    su vencimiento se corre con el uso. Por eso `require_owner` además compara `login_at` con el
    reloj y rechaza (y limpia) la sesión cuando pasan 12 h desde el login, aunque haya actividad.
    Se prueba congelando la fecha con `time-machine` (constitución II).
  - **Sobrevive a un reinicio**: la sesión vive firmada en la cookie, no en memoria. Mientras
    `SECRET_KEY` no cambie, un reinicio o un redeploy no la invalida.
- **Duración elegida: 12 h** (una jornada). Es una constante del módulo, sin variable de entorno
  (YAGNI). Si el dueño prefiere otra, se cambia en un solo sitio.
- **Limitación aceptada**: una sesión en cookie firmada no se puede revocar desde el servidor
  antes de que venza. Si se roba la cookie, vale hasta 12 h, salvo que se rote `SECRET_KEY` (R8)
  o se quite el correo de la lista (R6).

## R6. Lista blanca `OWNER_EMAILS`

- **Decisión**:
  - **Formato**: variable de entorno con correos separados por comas. `normalize_email` aplica
    `strip()` + `casefold()` a cada correo de la lista y al que entrega Google.
  - **Condiciones para entrar**: `email_verified` debe ser `true` y el correo normalizado debe
    estar en la lista.
  - **En cada petición**: `require_owner` vuelve a comprobar el correo de la sesión contra la
    lista. Quitar un correo cierra su acceso en la siguiente petición, tras el redeploy que
    cambia la variable.
  - **Producción**: no arranca si la lista está vacía o falta (R9).
- **Logs**: no registran el correo, que es un dato personal (constitución VI). Solo dicen
  «inicio de sesión aceptado» o «rechazado: no_autorizado» y similares.

## R7. OIDC con authlib 1.9: qué valida y qué no (verificado en el código fuente)

Revisado en `authlib/integrations/starlette_client/apps.py`, `base_client/sync_app.py` y
`base_client/async_openid.py` (versión 1.9.9). **Se declara aquí y se prueba**, no se da por
hecho:

- **`state` (sí lo valida)**:
  - `authorize_redirect` genera un `state` aleatorio y guarda en la sesión
    `_state_google_<state>` con `redirect_uri` y `nonce`.
  - En el callback, `authorize_access_token` busca esos datos por el `state` recibido. Si no
    existen, `_format_state_params` lanza `MismatchingStateError`.
  - Los datos se borran tras usarlos (`clear_state_data`), así que un `state` no se puede
    reutilizar.
- **`nonce` (lo valida, con una condición)**:
  - Con `openid` en el `scope`, authlib genera un `nonce` y lo guarda junto al `state`.
  - Al volver, **solo si** la respuesta trae `id_token` **y** el estado guardado tiene `nonce`,
    llama a `parse_id_token`. Esa función valida:
    - la firma con las claves públicas (JWKS) de Google;
    - `iss` contra el emisor de los metadatos;
    - `aud` contra el `client_id`;
    - `exp` e `iat`, con 120 s de margen;
    - el `nonce` (`CodeIDToken`).
  - **Si la respuesta no trae `id_token`, authlib no valida nada de eso y no devuelve
    `userinfo`.** Por eso `GoogleIdentityProvider.complete_login` exige `token["userinfo"]` y, si
    no está, lanza `LoginFailed("sin_id_token")`.
- **Errores**: authlib lanza `OAuthError` (incluido `MismatchingStateError`) y errores de
  `joserfc.errors` (authlib 1.9 valida el `id_token` con joserfc); la red puede lanzar
  `httpx2.HTTPError` (authlib 1.9 usa httpx2; R14). Todos se traducen a `LoginFailed` con un
  motivo corto. Al log va solo el tipo de excepción, nunca su mensaje: puede incluir el código de
  autorización o fragmentos del token.
- **Cómo se prueba**: además del proveedor falso de R3, una prueba unitaria de
  `GoogleIdentityProvider` corre authlib real contra un Google simulado con `httpx2.MockTransport`
  (metadatos, JWKS con una clave RSA generada en la prueba y endpoint de token). Comprueba que:
  - un `state` desconocido se rechaza;
  - un `id_token` con otro `nonce` se rechaza;
  - una respuesta sin `id_token` se rechaza;
  - un `id_token` válido da la identidad.

  Si authlib no permite inyectar el transporte por `client_kwargs`, se avisa en la fase roja
  antes de buscar otro mecanismo.

## R8. Rotación de `SECRET_KEY`

- **Qué pasa**: la firma de todas las cookies de sesión deja de ser válida. Starlette las ignora,
  así que **se invalidan todas las sesiones**: el dueño tiene que volver a entrar. También fallan
  los inicios de sesión que estaban a medio camino en Google, porque su `state` vive en la sesión
  vieja; el dueño ve «No se completó el inicio de sesión con Google» y reintenta.
- **Cuándo rotarla**: ante sospecha de filtración de la clave o de robo de una cookie de sesión.
  Es el único modo de cerrar todas las sesiones a la vez.
- **Cómo**: Render → Environment → `SECRET_KEY` → **Generate** → guardar y redeploy. No hay datos
  persistentes cifrados con esta clave, así que no se pierde nada más.

## R9. Configuración nueva

| Variable | Producción | Local | Pruebas |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | Obligatoria | Obligatoria solo para usar el login real | Valor ficticio |
| `GOOGLE_CLIENT_SECRET` | Obligatoria (`SecretStr`) | Igual que arriba | Valor ficticio |
| `OWNER_EMAILS` | Obligatoria, no vacía | Recomendable | `dueno@example.com` |
| `PUBLIC_BASE_URL` | Obligatoria, `https://`: `https://pedidofacil-6nky.onrender.com`; si falta, se usa `RENDER_EXTERNAL_URL`, que Render define | Por defecto `http://127.0.0.1:8000` | `http://testserver` |

- **Validación**: `_production_problems` (en `app/config.py`) agrega los faltantes con el mismo
  formato de hoy, sin mostrar valores.
- **Por qué hace falta `PUBLIC_BASE_URL`**: la URI de vuelta se construye desde esta variable y
  no desde la petición. Render termina el TLS en su proxy y `uvicorn` no confía por defecto en sus
  cabeceras `X-Forwarded-*`; `request.url_for` daría `http://…`, que no coincide con la URI
  registrada en Google.

## R10. URIs de redirección que hay que registrar en Google Cloud

En **Google Cloud Console → APIs y servicios → Credenciales → ID de cliente de OAuth (aplicación
web) → URIs de redireccionamiento autorizados**:

| Ambiente | URI |
|---|---|
| Local | `http://127.0.0.1:8000/auth/google/callback` |
| Local (alternativa) | `http://localhost:8000/auth/google/callback` |
| Producción | `https://pedidofacil-6nky.onrender.com/auth/google/callback` (la URL pública del servicio en Render, igual a `PUBLIC_BASE_URL`) |

- **Origen de JavaScript autorizado**: no hace falta, porque el flujo es solo del servidor.
- **Pantalla de consentimiento**: tipo externo, en modo **Testing**, con el correo del dueño
  agregado como usuario de prueba (ADR 0003).
- **Cuidado en local**: abrir la app en el mismo host que `PUBLIC_BASE_URL`. Si la app se abre en
  `localhost` y la URI de vuelta es `127.0.0.1`, la cookie con el `state` no viaja al callback y
  el login falla con «No se completó…».

## R11. Mensajes en la página de login

- **Decisión**: el callback y el logout redirigen a `/login?aviso=<código>`. La plantilla traduce
  el código a un mensaje fijo:
  - `no_autorizado` → «Esta cuenta de Google no tiene acceso a PedidoFácil»
  - `cancelado` → «No se completó el inicio de sesión con Google»
  - `error` → «No se pudo iniciar sesión con Google. Intenta de nuevo»
  - `salida` → «Cerraste sesión»

  Un código desconocido no muestra nada.
- **Justificación**: nunca se refleja texto que venga en la URL ni del proveedor. Así no hay
  inyección de contenido ni se filtran detalles técnicos (FR-003, FR-011).

## R12. Dependencias

- **`authlib`**: integración OAuth 2.0 y OIDC con Starlette (ADR 0003). Trae `cryptography`, que
  hace falta para verificar firmas RS256.
- **`itsdangerous`**: la exige `SessionMiddleware` para firmar la cookie; hoy no está instalada.
- **`time-machine`** (desarrollo): congela el reloj en las pruebas de caducidad, como manda la
  constitución (II).
- **`pwdlib`**: no se agrega (ADR 0003).

## R13. Documentación automática apagada en producción

- **Decisión**: en producción, `docs_url`, `redoc_url` y `openapi_url` valen `None`; en `local` y
  `test` se conservan (`/docs`, `/redoc`, `/openapi.json`).
  - **Ya está implementado** desde PED-11 (`app/main.py`, `settings.docs_enabled`) y lo prueba
    `tests/integration/test_docs.py`. Esta historia lo **ratifica** y no cambia el código.
  - **Dependencia nueva de esa decisión**: la prueba de cobertura de rutas (R2) usa la app de
    producción y no tiene excepciones para la documentación. Si algún día se encendiera la
    documentación en producción, esa prueba fallaría, porque sus rutas no son `APIRoute`.
- **Justificación**:
  - las rutas de documentación de FastAPI son rutas de Starlette y no pasan por `require_owner`
    (R1);
  - publicarlas expondría la lista completa de endpoints, incluidos los protegidos.

  En desarrollo siguen siendo útiles y no hay datos reales.

## R14. Dos bibliotecas HTTP: httpx y httpx2

**Hechos** (verificados el 2026-11-18 en el entorno instalado):

| Biblioteca | Versión | Quién la usa | Por qué está instalada |
|---|---|---|---|
| `httpx` | 0.28 | Ningún código del proyecto todavía | La trae `fastapi[standard]` (y `fastapi-cloud-cli`) |
| `httpx2` | 2.16 | `TestClient` de Starlette y el cliente OAuth de authlib 1.9 | La trae `fastapi[standard]` |

- **`TestClient` usa httpx2**: `starlette/testclient.py` hace `import httpx2 as httpx` y solo
  recurre a `httpx` si `httpx2` falta. Por eso las pruebas ya tipan las respuestas como
  `httpx2.Response` (`tests/integration/test_catalog_pages.py`, `tests/doubles.py`).
- **authlib 1.9 usa httpx2** (`authlib/integrations/httpx_client/_compat.py`). Si `httpx2` falta,
  recurre a `httpx` con un aviso de obsolescencia. **No declara ninguna de las dos** como
  dependencia: su metadata solo pide `cryptography` y `joserfc`.
- **Consecuencia para las pruebas de authlib**: el transporte que se inyecta en authlib
  (`client_kwargs={"transport": ...}`) debe ser `httpx2.MockTransport`, y sus errores de red son
  `httpx2.HTTPError`.

**Regla**:

- **Código propio de producción**: usa `httpx` y se prueba con `httpx.MockTransport`, como
  manda la constitución (principio II). Esto incluye la futura integración con la Bot API de
  Telegram (principio IV); cuando llegue, `httpx` se declara con `uv add httpx`.
- **`httpx2` en las pruebas**: aparece solo por dependencias ajenas, en dos casos:
  - para tipar las respuestas de `TestClient` (`httpx2.Response`);
  - como `httpx2.MockTransport` en las pruebas que ejercitan authlib por dentro
    (`tests/unit/test_google_identity.py`).
- **`httpx2` en `app/`**: solo en `app/services/identity.py`, para tipar el transporte que se le
  pasa a authlib. Ningún otro módulo de la app la importa.

**Dependencias declaradas** (actualizado el 2026-11-18):

- **`httpx2`** se declara directamente (`uv add httpx2`). La importa `app/services/identity.py`
  y es la que usa authlib, así que el proyecto ya no depende de que `fastapi[standard]` la siga
  trayendo.
- **`httpx`** sigue llegando solo de forma transitiva; se declarará con `uv add httpx` cuando
  llegue la integración con Telegram, el primer código propio que la importe.
