---
description: "Tareas de PED-15 · HU-07 Acceso protegido del dueño"
---

# Tareas: PED-15 · HU-07 Acceso protegido del dueño

**Entrada**: documentos de diseño en `specs/003-acceso-protegido-dueno/`

**Prerrequisitos**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Pruebas**: obligatorias (TDD estricto, principio I). Cada fase sigue el mismo ciclo:

1. **Rojo**: se escriben todas las pruebas de la fase, con esqueletos de lo que aún no existe
   (firma tipada y `raise NotImplementedError`). Las líneas que referencian atributos
   inexistentes llevan `# type: ignore[<código>]`.
2. Se ejecuta `uv run pytest`. Cada prueba nueva DEBE fallar por la razón esperada: una aserción
   o un `NotImplementedError`, nunca `ImportError` ni un error de sintaxis.
3. **⛔ ALTO — revisión del autor**: no se escribe código de producción hasta que el autor
   apruebe las pruebas. Tras la aprobación, commit `test(PED-15): …`.
4. **Verde**: el código mínimo para que pase todo. Con `uv run pytest`, `uv run ruff check .` y
   `uv run mypy` en verde, commit `feat(PED-15): …`.
5. **Refactor** (si aplica): con todo en verde, commit `refactor(PED-15): …`.

**Organización**: preparación, fundamentos y las cuatro historias de la spec en su orden
(US1–US4), más una fase de pulido.

## Formato: `[ID] [P?] [Historia] Descripción`

- **[P]**: puede hacerse en paralelo (archivos distintos, sin dependencias pendientes).
- **[USn]**: historia de la spec a la que pertenece.
- **⛔ ALTO**: punto de revisión obligatorio de la fase roja.
- Rutas relativas a la raíz del repositorio.

## Convenciones para las pruebas

- **Nunca se llama a Google** (constitución II):
  - **Pruebas de flujo**: usan `FakeIdentityProvider` (en `tests/doubles.py`) mediante
    `app.dependency_overrides[get_identity_provider]`.
    - `start_login` responde `RedirectResponse("/auth/google/callback?state=falso",
      status_code=302)`.
    - `complete_login` devuelve la `VerifiedIdentity` configurada o lanza el `LoginFailed`
      configurado.
  - **`GoogleIdentityProvider`**: se prueba solo contra `httpx2.MockTransport`, porque authlib 1.9 usa httpx2 (research.md R14).
- **Reloj**: las pruebas de caducidad usan `time_machine.travel(...)` (constitución II).
- **Tokens centinela**: los valores falsos de tokens empiezan por `TOKEN-CENTINELA-`. Las pruebas
  verifican que no aparecen en `caplog`, en el cuerpo de las respuestas ni en la sesión
  decodificada.
- **Leer la sesión en una prueba**: decodificar la cookie con
  `itsdangerous.TimestampSigner(SECRET_KEY)` + `base64` + `json` (así firma Starlette).
- **Nombres**: las pruebas se nombran en español; los identificadores, en inglés.
- **`tests/conftest.py` y archivos de prueba ya existentes**: el hook `guard_files.py` pide
  confirmación al editarlos. Solo se amplían; nunca se cambia una aserción existente.

---

## Fase 1: Preparación

**Propósito**: dependencias justificadas en research.md R12; no cambia el comportamiento.

- [X] T001 Agregar dependencias con `uv add authlib itsdangerous` y `uv add --dev time-machine` (actualiza `pyproject.toml` y `uv.lock`). Verificar `uv run pytest` en verde y hacer commit `chore(PED-15): agregar authlib, itsdangerous y time-machine`

---

## Fase 2: Fundamentos (bloquean todas las historias)

**Propósito**: configuración del login (contracts/configuration.md) y normalización de correos,
que usan todas las historias.

### Pruebas de los fundamentos (rojo) ⚠️

- [X] T002 [P] Prueba en `tests/unit/test_config.py` (ampliar), según contracts/configuration.md:
  - **Lista blanca**: `OWNER_EMAILS=" Dueno@Gmail.com , otro@x.co ,,"` da `owner_emails == frozenset({"dueno@gmail.com", "otro@x.co"})`.
  - **`PUBLIC_BASE_URL` por defecto**: vale `"http://127.0.0.1:8000"` en `local` y `"http://testserver"` en `test`.
  - **Fallback de Render**: sin `PUBLIC_BASE_URL` y con `RENDER_EXTERNAL_URL="https://pedidofacil-6nky.onrender.com"` en producción, `public_base_url` toma ese valor.
  - **Validación de producción**: el error nombra `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_EMAILS` (si falta o queda vacía tras normalizar) y `PUBLIC_BASE_URL` (si falta o no empieza por `https://`).
  - **Privacidad**: `str(error)` no contiene el valor de `GOOGLE_CLIENT_SECRET` (usar `"secreto-centinela"`).
  - **Redirección**: la propiedad `oauth_redirect_uri` da `f"{public_base_url}/auth/google/callback"`.
- [X] T003 [P] Prueba en `tests/unit/test_auth_service.py` (nuevo) para `normalize_email`: `"  Dueno@Gmail.COM "` → `"dueno@gmail.com"`; `""` → `""`.
- [X] T004 Ampliar las fixtures y la prueba del ejemplo de configuración:
  - **`test_settings`** (en `tests/conftest.py`): agregarle `google_client_id="test-client-id"`, `google_client_secret="test-client-secret"`, `owner_emails="dueno@example.com"` y `secret_key="s" * 32` (fija, para poder decodificar la sesión).
  - **`production_settings`** (en `tests/conftest.py`): agregarle con `monkeypatch.setenv` `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_EMAILS=dueno@example.com` y `PUBLIC_BASE_URL=https://pedidofacil-6nky.onrender.com`.
  - **`tests/unit/test_env_example.py`**: agregar `"GOOGLE_CLIENT_SECRET"` a `MUST_BE_COMMENTED` y `"RENDER_EXTERNAL_URL"` a `PLATFORM_VARIABLES`.

**⛔ ALTO — revisión de la fase roja de los fundamentos.** Ejecutar `uv run pytest`, mostrar que
T002–T003 fallan por la razón esperada y que las pruebas existentes siguen en verde. Esperar la
aprobación del autor. Luego, commit `test(PED-15): configuración del login y normalización de correos`.

### Implementación de los fundamentos (verde)

- [X] T005 Implementar `normalize_email(email: str) -> str` (`strip()` + `casefold()`) en `app/services/auth.py`, un módulo puro que no importa `app.config`.
- [X] T006 Implementar en `app/config.py`:
  - **Campos nuevos**:
    - `google_client_id: str | None`;
    - `google_client_secret: SecretStr | None`;
    - `owner_emails: Annotated[frozenset[str], NoDecode]`, con un validador `mode="before"` que separa por comas, aplica `normalize_email` y descarta vacíos;
    - `public_base_url: str | None`, con `validation_alias=AliasChoices("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL")`.
  - **Defaults por ambiente** de `public_base_url`.
  - **Faltantes en producción**: agregarlos a `_production_problems`.
  - **Propiedad** `oauth_redirect_uri`.
  - **`.env.example`**: documentar las cuatro variables nuevas sin valores reales (`GOOGLE_CLIENT_SECRET` comentada).
  - Commit `feat(PED-15): …`.

**Punto de control**: configuración lista; `uv run pytest` en verde.

---

## Fase 3: Historia 1 - Entrar con la cuenta de Google (P1) 🎯 MVP

**Objetivo**: entrar con Google y volver a la página pedida con la sesión iniciada; la sesión no
guarda tokens; la cookie es `HttpOnly`, `SameSite=lax` y `Secure` en producción.

**Prueba independiente**: con el proveedor falso, completar el login con un correo autorizado y
abrir el catálogo.

### Pruebas de la Historia 1 (rojo) ⚠️

- [X] T007 [P] [US1] Prueba en `tests/unit/test_auth_service.py` para `safe_next_path(raw: str | None) -> str | None` (research.md R4), con dos pruebas parametrizadas (`@pytest.mark.parametrize`). Los valores se escriben en Python como literales crudos (`r"..."`) donde haya barras invertidas:
  - **Se aceptan y devuelven igual**: `"/productos/7"`, `"/productos?x=1"`, `"/productos"` y `"/productos?inactivos=1"`.
  - **Se rechazan (dan `None`)**:
    - los cinco casos pedidos por el autor: `"https://evil.com"`, `"//evil.com"`, `r"/\evil.com"`, `r"\\evil.com"` y `r"https:/\evil.com"`;
    - además: `None`, `""`, `"productos"`, `"//evil.com/productos"`, `r"/productos\x"`, `"http:/evil.com"`, `"javascript:alert(1)"`, `"/login"`, `"/login/google"`, `"/auth/google/callback"`, `"/logout"`, `"/productos\n"` y `"/productos\t"`.
- [X] T008 [P] [US1] Prueba en `tests/unit/test_auth_service.py` para `start_session(session: dict[str, Any], identity: VerifiedIdentity, now: float) -> None`. Con una sesión que ya trae `{"basura": 1, "_state_google_x": {...}, "login_next": "/productos"}`, después de llamarla la sesión es exactamente `{"owner": {"email": "dueno@example.com", "name": "Dueño", "login_at": now}}`: se limpió antes de escribir (R5) y no trae tokens.
- [X] T009 [P] [US1] Prueba en `tests/integration/test_login_flow.py` (nuevo). Usa `create_app(test_settings)` + `FakeIdentityProvider` en `dependency_overrides` y un `TestClient` sin sesión:
  - `GET /login` → 200 con un enlace o botón a `/login/google` con el texto «Entrar con Google» y sin ningún `type="password"`.
  - `GET /login/google?next=/productos/7` → 302 hacia el proveedor (el falso apunta al callback); al seguir al callback con la identidad `dueno@example.com` verificada → 303 con `Location: /productos/7`.
  - Sin `next` → el callback redirige a `/productos`.
  - `GET /login/google?next=//evil.com` → tras el callback, `Location: /productos`.
  - Tras entrar, `GET /productos` → 200 y la navegación muestra «Dueño» (el nombre de la identidad).
  - Con sesión, `GET /login` → 303 a `/productos`.
  - La sesión decodificada contiene solo `owner` con `email`, `name` y `login_at`, sin `TOKEN-CENTINELA-` (el proveedor falso adjunta un token centinela que no debe pasar a la sesión).
  - **Login sin configurar en local (G1, contracts/configuration.md)**:
    - **Montaje**: una app con `Settings(_env_file=None, environment="local", database_url="sqlite://")` y sin `GOOGLE_CLIENT_ID`. Se sustituye `get_identity_provider` por `ExplodingIdentityProvider`, que hace fallar la prueba si se le llama: así se prueba que no se intenta contactar a Google (cambio 3 de la fase roja, abajo).
    - **Resultado**: `GET /login/google` → 303 a `/login?aviso=error`. Al seguirla, la página muestra «No se pudo iniciar sesión con Google. Intenta de nuevo» y no queda sesión con `owner`.
- [X] T010 [P] [US1] Prueba en `tests/integration/test_session_cookie.py` (nuevo). Tras un login con el proveedor falso, la cabecera `Set-Cookie` de `pedidofacil_session` contiene:
  - `HttpOnly`, `SameSite=lax`, `Max-Age=43200` y `Path=/`;
  - **sin `Secure`** en `test`;
  - **con `Secure`** en la app de producción: `create_app(production_settings)` con `get_session` y `get_identity_provider` sustituidos.
- [X] T011 [P] [US1] Prueba en `tests/unit/test_google_identity.py` (nuevo), con authlib real contra `httpx2.MockTransport` (research.md R7 y R14):
  - **Google simulado**: el transporte responde `/.well-known/openid-configuration` (issuer `https://accounts.google.com`, endpoints falsos), el JWKS con una clave RSA generada en la prueba (`joserfc.jwk.RSAKey.generate_key(2048, parameters={"kid": ...})`) y el endpoint de token con un `id_token` firmado (`iss`, `aud=test-client-id`, `exp`, `iat`, `email`, `email_verified=True`, `name`, `nonce` igual al guardado) más `access_token="TOKEN-CENTINELA-ACCESO"`.
  - **Ida**: `start_login(request, redirect_uri)` responde 302 hacia el endpoint de autorización con `state` y `nonce` en la URL, y los guarda en la sesión.
  - **Vuelta**: `complete_login` con ese `state` devuelve `VerifiedIdentity(email="dueno@example.com", email_verified=True, name="Dueño")`.
  - **Si authlib no deja inyectar el transporte** (`client_kwargs={"transport": ...}` en `OAuth.register`): detenerse y avisar al autor en esta misma fase roja, sin buscar otro mecanismo por cuenta propia.
- [X] T012 [US1] Agregar a `tests/doubles.py` el `FakeIdentityProvider` tipado (ver convenciones) y, en `tests/conftest.py`, las fixtures `identity_provider`, `auth_app` y `anonymous_client`; en `tests/doubles.py`, `log_in(client, next_path)`, `read_session` y `ExplodingIdentityProvider` (ver los cambios aplicados abajo). Agregar los esqueletos con `NotImplementedError`:
  - en `app/services/identity.py`: `VerifiedIdentity`, `LoginFailed`, `IdentityProvider`, `GoogleIdentityProvider`, `get_identity_provider`;
  - en `app/services/auth.py`: `safe_next_path`, `start_session`.

**Cambios aplicados en la fase roja de US1** (2026-11-18, aprobados por el autor):

1. **`log_in` es una función tipada** en `tests/doubles.py` (`log_in(client, next_path=None)`), no una fixture `login` de `conftest`, para usarla con cualquier cliente.
2. **`anonymous_client` (con `auth_app` e `identity_provider`) se adelanta a T012**, porque US1 ya necesita un cliente sin sesión con el proveedor falso. La fixture `client` del catálogo no cambia hasta T026.
3. **G1 sustituye el proveedor por `ExplodingIdentityProvider`**: la app local real sin `GOOGLE_CLIENT_ID` y un proveedor que hace fallar la prueba si se le llama. Inyectar un `MockTransport` en el proveedor de la app habría exigido cambiar `create_app` solo para la prueba, y así se verifica algo más fuerte: que ni siquiera se usa el proveedor.
4. **Claves y firma del `id_token` con `joserfc`** (`RSAKey.generate_key`, `jwt.encode`), la biblioteca JOSE que trae authlib 1.9, en lugar de `authlib.jose`.
5. **Tipos de error reales para T022**: `joserfc.errors.*` y `httpx2.HTTPError` (ya corregidos en T022).

**⛔ ALTO — revisión de la fase roja de la Historia 1.** Ejecutar `uv run pytest`, mostrar que
T007–T011 fallan por la razón esperada (sin `ImportError`) y esperar la aprobación del autor.
Luego, commit `test(PED-15): entrar con la cuenta de Google`.

### Implementación de la Historia 1 (verde)

- [X] T013 [US1] Implementar `safe_next_path` y `start_session` en `app/services/auth.py` según research.md R4 y R5.
- [X] T014 [US1] Implementar en `app/services/identity.py`:
  - `VerifiedIdentity` (frozen: `email: str`, `email_verified: bool`, `name: str`).
  - `LoginFailed(reason: str)`.
  - El protocolo `IdentityProvider`.
  - `GoogleIdentityProvider(settings, transport: httpx.AsyncBaseTransport | None = None)`: registra en authlib `google` con `server_metadata_url`, `client_id`, `client_secret` y `client_kwargs={"scope": "openid email profile"}` más el transporte si se pasa. `complete_login` llama a `authorize_access_token` y exige `token.get("userinfo")`.
  - `get_identity_provider(request) -> IdentityProvider`, que lo lee de `request.app.state`.
- [X] T015 [US1] Implementar en `app/main.py` el `SessionMiddleware`:
  - **Parámetros**: `secret_key=settings.secret_key`, `session_cookie="pedidofacil_session"`, `max_age=SESSION_MAX_AGE_SECONDS` (`12 * 60 * 60`, constante en `app/security.py`), `same_site="lax"` y `https_only=settings.environment == "production"`.
  - **`app.state.identity_provider`**: guardar ahí `GoogleIdentityProvider(settings)`.
- [X] T016 [US1] Implementar `app/routers/auth.py` y sus plantillas, y registrar el router en `app/main.py`:
  - **`GET /login`**: si ya hay sesión, 303 a `safe_next_path(next)` o `/productos`; si no, 200 con `app/templates/auth/login.html`.
  - **`GET /login/google`**: si `settings.google_client_id` o `settings.google_client_secret` faltan (solo posible fuera de producción, que no arranca sin ellos), registra un WARNING «login con Google sin configurar» y responde 303 a `/login?aviso=error` sin crear el proveedor ni hacer peticiones (G1). Si están, guarda `session["login_next"] = safe_next_path(next)` y devuelve `provider.start_login(request, settings.oauth_redirect_uri)`.
  - **`GET /auth/google/callback`**: llama a `provider.complete_login`; con éxito, lee `login_next`, llama a `start_session(request.session, identity, time.time())` y responde 303 a ese destino (revalidado con `safe_next_path`) o a `/productos`.
  - **`app/templates/base.html`**: con sesión, la navegación muestra el nombre del dueño.

**Punto de control**: US1 en verde. El acceso todavía **no** está restringido (llega en US2 y
US3): no desplegar.

---

## Fase 4: Historia 2 - Rechazar a quien no está autorizado (P1)

**Objetivo**: solo entran correos verificados de la lista blanca; cualquier fallo termina en el
login con un mensaje fijo y sin sesión.

**Prueba independiente**: con el proveedor falso, entrar con un correo fuera de la lista y
comprobar el mensaje y que no hay sesión.

### Pruebas de la Historia 2 (rojo) ⚠️

- [ ] T017 [P] [US2] Prueba en `tests/unit/test_auth_service.py` para `is_authorized(identity: VerifiedIdentity, owner_emails: frozenset[str]) -> bool`:
  - `True` para `"Dueno@Example.com "` verificado si la lista tiene `"dueno@example.com"`;
  - `False` si el correo no está;
  - `False` si `email_verified=False` aunque esté en la lista.
- [ ] T018 [P] [US2] Ampliar `tests/integration/test_login_flow.py`. Los casos, con el aviso al que redirige el callback, el mensaje exacto en `GET /login?aviso=…` (contracts/auth-routes.md) y sin sesión (`GET /productos` sin 200 y la sesión decodificada sin `owner`):

  | Caso | Aviso | Mensaje |
  |---|---|---|
  | Identidad verificada `intruso@gmail.com` | `no_autorizado` | «Esta cuenta de Google no tiene acceso a PedidoFácil» |
  | `dueno@example.com` con `email_verified=False` | `no_autorizado` | El mismo |
  | `LoginFailed("cancelado")` | `cancelado` | «No se completó el inicio de sesión con Google» |
  | `LoginFailed("state_invalido")` | `cancelado` | El mismo |
  | `LoginFailed("red")` | `error` | «No se pudo iniciar sesión con Google. Intenta de nuevo» |
  | `LoginFailed("sin_id_token")` | `error` | El mismo |

  Además:
  - `GET /login?aviso=<script>` no refleja el texto y no muestra ningún aviso.
  - En los rechazos, ni `caplog` ni las respuestas contienen `intruso@gmail.com` ni `TOKEN-CENTINELA-`.
- [ ] T019 [P] [US2] Ampliar `tests/unit/test_google_identity.py`. Cada caso debe lanzar `LoginFailed` con el motivo indicado:

  | Caso | Motivo |
  |---|---|
  | Callback con un `state` que no está en la sesión | `state_invalido` |
  | El mismo `state` usado dos veces | `state_invalido` |
  | `id_token` con un `nonce` distinto | `id_token_invalido` |
  | `id_token` firmado con otra clave | `id_token_invalido` |
  | `aud` distinto de `test-client-id` | `id_token_invalido` |
  | Respuesta de token sin `id_token` | `sin_id_token` (la condición de R7) |
  | `?error=access_denied` | `cancelado` |
  | El transporte lanza `httpx.ConnectError` | `red` |

  Además: en todos los casos, `caplog` no contiene `TOKEN-CENTINELA-` ni el `code` de la URL.
- [ ] T020 [US2] Esqueleto de `is_authorized` con `NotImplementedError` en `app/services/auth.py`.

**⛔ ALTO — revisión de la fase roja de la Historia 2.** Ejecutar `uv run pytest`, mostrar que
T017–T019 fallan por la razón esperada y esperar la aprobación del autor. Luego, commit
`test(PED-15): rechazar cuentas no autorizadas`.

### Implementación de la Historia 2 (verde)

- [ ] T021 [US2] Implementar `is_authorized` en `app/services/auth.py`.
- [ ] T022 [US2] Implementar en `GoogleIdentityProvider.complete_login` (`app/services/identity.py`) la traducción de errores a `LoginFailed` (contracts/auth-routes.md):
  - `OAuthError` con `error == "access_denied"` → `cancelado`;
  - `MismatchingStateError` → `state_invalido`;
  - errores de `joserfc.errors.*` (por ejemplo `InvalidClaimError` con un `nonce` distinto, `BadSignatureError` con otra clave) → `id_token_invalido`. authlib 1.9 valida el `id_token` con joserfc, no con `authlib.jose`;
  - `httpx2.HTTPError` → `red`. authlib 1.9 usa httpx2, no httpx (research.md R14);
  - sin `userinfo` → `sin_id_token`.

  El log solo registra `type(error).__name__` y el motivo.
- [ ] T023 [US2] Implementar en `app/routers/auth.py` y `app/templates/auth/login.html`:
  - **Callback**: si `LoginFailed` o `not is_authorized(identity, settings.owner_emails)`, hace `request.session.clear()` y responde 303 a `/login?aviso=<código>`.
  - **Plantilla**: traduce solo los códigos conocidos (`no_autorizado`, `cancelado`, `error`, `salida`) con un diccionario fijo.
  - **Logs**: registran «inicio de sesión aceptado» o «rechazado: <motivo>», sin el correo.

**Punto de control**: US1 y US2 en verde. Las rutas de gestión todavía no exigen sesión: no
desplegar.

---

## Fase 5: Historia 3 - Gestión siempre protegida (P1)

**Objetivo**: denegar por defecto. `require_owner` se aplica en toda la app y solo `PUBLIC_PATHS`
queda abierta. La lista blanca se revisa en cada petición.

**Prueba independiente**: recorrer `app.routes` de la app de producción sin sesión.

### Pruebas de la Historia 3 (rojo) ⚠️

- [ ] T024 [P] [US3] Prueba en `tests/integration/test_route_protection.py` (nuevo), según research.md R2. Usa `create_app(production_settings)` con `dependency_overrides` para `get_session` (`FailingSession` de `tests/doubles.py`) y `get_identity_provider` (el falso), y una constante local `EXPECTED_PUBLIC = {"/health", "/health/live", "/login", "/login/google", "/auth/google/callback"}`, duplicada a propósito.
  - **Rutas que no son `APIRoute`**: si hay alguna, la prueba falla con su path. Sin excepciones: en producción no hay documentación (R13).
  - **Rutas protegidas**: para cada `APIRoute` fuera de `EXPECTED_PUBLIC` y cada método salvo `HEAD`, la petición sin sesión (con `{param}` reemplazado por `1` y `follow_redirects=False`) responde 303 con `Location` que empieza por `/login`.
  - **Rutas públicas**: cada una responde sin `Location` hacia `/login`.
  - **Lista pública**: `app.security.PUBLIC_PATHS == EXPECTED_PUBLIC`.
- [ ] T025 [P] [US3] Ampliar `tests/integration/test_login_flow.py`:
  - Sin sesión, `GET /productos` → 303 a `/login?next=%2Fproductos` (o `next=/productos`, según cómo se codifique), y `GET /productos/3` → `next` con ese path.
  - Sin sesión, `POST /productos` con datos válidos → 303 a `/login` sin `next`; luego, con sesión, `/productos` no muestra ese producto (no se guardó).
  - Sin sesión, `/health` y `/health/live` responden como hoy (200).
  - **Lista blanca revisada en cada petición**: login con `OWNER_EMAILS=dueno@example.com`; se reconstruye la app con la misma `SECRET_KEY` y `OWNER_EMAILS=otro@example.com`, se reutiliza la cookie y `GET /productos` responde 303 al login.
  - **Cookie alterada**: un byte cambiado → 303 al login, sin error 500.
- [ ] T026 [US3] Actualizar las fixtures en `tests/conftest.py`:
  - **`client`**: pasa a tener sesión iniciada con el proveedor falso (usa la función `log_in` de `tests/doubles.py`, T012). Así `tests/integration/test_catalog_pages.py` sigue sin tocarse.
  - **`anonymous_client`**: ya existe desde la fase roja de US1 (T012).
  - **Comprobación**: con la protección aún sin implementar, las pruebas del catálogo siguen pasando con `client`.
- [ ] T027 [US3] Esqueleto `app/security.py` con `PUBLIC_PATHS`, `SESSION_MAX_AGE_SECONDS` (si no existe ya por T015), `LoginRequired` y `require_owner` (`NotImplementedError`), y esqueleto de `current_owner(session, owner_emails, now) -> dict[str, Any] | None` en `app/services/auth.py`.

**⛔ ALTO — revisión de la fase roja de la Historia 3.** Ejecutar `uv run pytest`, mostrar que
T024–T025 fallan por la razón esperada y que las pruebas del catálogo siguen en verde con el
`client` autenticado. Esperar la aprobación del autor. Luego, commit
`test(PED-15): gestión protegida por defecto`.

### Implementación de la Historia 3 (verde)

- [ ] T028 [US3] Implementar `current_owner(session, owner_emails, now)` en `app/services/auth.py`. Devuelve el `owner` si existe y su correo sigue en la lista blanca (R6); si no, devuelve `None`. La caducidad llega en US4.
- [ ] T029 [US3] Implementar `app/security.py`:
  - **`require_owner(request)`**: si `request.url.path in PUBLIC_PATHS`, sale. Si no, llama a `current_owner(...)`; sin dueño, hace `request.session.clear()` y lanza `LoginRequired(next_path)`, con el path y la query solo si el método es `GET`. Con dueño, guarda el owner en `request.state.owner`.
  - **En `app/main.py`**: registrar `FastAPI(dependencies=[Depends(require_owner)])` y un manejador de `LoginRequired` que responde 303 a `/login` (con `?next=` URL-codificado si aplica).
  - **`base.html`**: lee el dueño de `request.state.owner`.

**Punto de control**: US1–US3 en verde. El acceso ya está protegido; falta el cierre de sesión
(US4) para cumplir la spec completa.

---

## Fase 6: Historia 4 - Cerrar sesión y caducidad (P2)

**Objetivo**: cerrar sesión solo por `POST`; caducidad absoluta de 12 h desde el login; la sesión
sobrevive a un reinicio mientras no cambie `SECRET_KEY`.

**Prueba independiente**: entrar, cerrar sesión y comprobar que el catálogo exige login; con el
reloj simulado, comprobar la caducidad.

### Pruebas de la Historia 4 (rojo) ⚠️

- [ ] T030 [P] [US4] Ampliar `tests/unit/test_auth_service.py`:
  - **Caducidad absoluta**: `current_owner` con `login_at = t0` devuelve el dueño en `t0 + 12 h - 1 s` y `None` en `t0 + 12 h + 1 s`, aunque haya actividad en medio (R5). Usar `time_machine.travel` o pasar `now` explícito.
  - **`end_session(session)`**: deja la sesión vacía (`{}`), incluida cualquier clave ajena.
- [ ] T031 [P] [US4] Ampliar `tests/integration/test_login_flow.py`:
  - **Cerrar sesión**: con sesión, `POST /logout` → 303 a `/login?aviso=salida`. La página muestra «Cerraste sesión», la respuesta envía la cookie vencida o vacía, y después `GET /productos` responde 303 al login.
  - **Sin cierre por `GET`**: con sesión, `GET /logout` → 405, y `GET /productos` sigue respondiendo 200 (R5: CSRF de cierre de sesión).
  - **Navegación**: con sesión, el HTML de `/productos` contiene `<form method="post" action="/logout">` con el botón «Cerrar sesión».
  - **Sobrevive a un reinicio**: con `time_machine.travel` fijo, login; se crea una app nueva con la misma configuración (misma `SECRET_KEY`) y se reutiliza la cookie: `GET /productos` → 200.
  - **Rotación de `SECRET_KEY`**: lo mismo con otra `SECRET_KEY` → 303 al login (R8).
  - **Caducidad absoluta con la cookie deslizante viva**: con `time_machine.travel(t0, tick=False)` y `traveller.move_to(...)`:
    - login en `t0`;
    - `GET /productos` a `t0 + 2 h`, `t0 + 6 h` y `t0 + 11 h` responde 200 cada vez, y en cada respuesta llega un `Set-Cookie` de `pedidofacil_session` (Starlette renueva la cookie y su `Max-Age`, así que sin tope absoluto la sesión seguiría viva hasta `t0 + 23 h`);
    - `GET /productos` a `t0 + 12 h + 1 s` responde 303 al login, y la sesión decodificada queda vacía.

    **Esta prueba DEBE fallar si se elimina el tope absoluto** (la comparación con `login_at` en `current_owner`): sin él, la petición de las 12 h + 1 s respondería 200 porque la cookie se renovó a las 11 h. Para comprobarlo en la fase verde, comentar temporalmente el tope, ver la prueba en rojo y restaurarlo (no se hace commit de ese paso).
- [ ] T032 [US4] Esqueleto de `end_session` con `NotImplementedError` en `app/services/auth.py`.

**⛔ ALTO — revisión de la fase roja de la Historia 4.** Ejecutar `uv run pytest`, mostrar que
T030–T031 fallan por la razón esperada y esperar la aprobación del autor. Luego, commit
`test(PED-15): cerrar sesión y caducidad`.

### Implementación de la Historia 4 (verde)

- [ ] T033 [US4] Implementar `end_session` y la caducidad absoluta en `current_owner` (`now - login_at >= SESSION_MAX_AGE_SECONDS` → `None`) en `app/services/auth.py`.
- [ ] T034 [US4] Implementar `POST /logout` en `app/routers/auth.py`: llama a `end_session(request.session)` y responde 303 a `/login?aviso=salida`; sin ruta `GET`. En `app/templates/base.html`, agregar el formulario `POST /logout` con el botón «Cerrar sesión».

**Punto de control**: las cuatro historias en verde.

---

## Fase 7: Pulido y temas transversales

- [ ] T035 [P] Actualizar `docs/despliegue.md`:
  - variables nuevas en la tabla de Render (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_EMAILS`, `PUBLIC_BASE_URL=https://pedidofacil-6nky.onrender.com`);
  - sección «Google Cloud», con la pantalla de consentimiento en modo Testing, el usuario de prueba y las URIs de research.md R10;
  - sección «Rotar `SECRET_KEY`» (R8: invalida todas las sesiones y los logins en curso);
  - en «Riesgos aceptados», marcar como cerrado el riesgo de `/productos` público y levantar el límite de HU-04.
- [ ] T036 [P] Actualizar `README.md`: cómo configurar el login en local (`.env` con las variables de Google, abrir la app en el mismo host que `PUBLIC_BASE_URL`) y que las pruebas no necesitan credenciales.
- [ ] T037 Ejecutar `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy`; confirmar cobertura ≥ 80 % con ramas y buscar `TOKEN-CENTINELA` en la salida completa de pytest (`-s`), donde no debe aparecer.
- [ ] T038 Validar a mano [quickstart.md](quickstart.md), recorrido local 1–7, con un cliente OAuth real de Google.
- [ ] T039 Pasos manuales del autor **antes de integrar en `main`**: en Google Cloud, registrar `https://pedidofacil-6nky.onrender.com/auth/google/callback`; en Render, definir `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OWNER_EMAILS` y `PUBLIC_BASE_URL`. Sin ellas, la app no arranca en producción, por diseño. **Después del merge**: verificar la sección «Producción» de quickstart.md.

---

## Dependencias y orden de ejecución

### Entre fases

- **F1 → F2 → US1 → US2 → US3 → US4 → F7**, en el orden de la spec.
- **US2** depende de US1 (el callback y la plantilla de login).
- **US3** depende de US1 (la función `log_in` y el `client` autenticado) y de los fundamentos
  (`owner_emails`).
- **US4** depende de US3 (`current_owner` y la redirección al login).
- **Despliegue**: no se despliega hasta completar US3. Antes, el login existe pero no protege
  nada.

### Dentro de cada fase

- Pruebas y esqueletos (rojo) → **⛔ ALTO** → commit `test` → implementación (verde) → commit
  `feat`.
- Archivos compartidos entre fases (no paralelizar tareas que comparten archivo):
  - `app/services/auth.py`: T005, T013, T021, T028, T033;
  - `app/routers/auth.py`: T016, T023, T034;
  - `app/main.py`: T015, T016, T029;
  - `tests/integration/test_login_flow.py`: T009, T018, T025, T031;
  - `tests/conftest.py`: T004, T012, T026.

### Oportunidades de paralelismo

- F2: T002 y T003.
- US1: T007, T008, T009, T010 y T011 (T007 y T008 van en el mismo archivo: escribirlas juntas).
- US2: T017, T018 y T019.
- US3: T024 y T025.
- US4: T030 y T031.
- F7: T035 y T036.

## Ejemplo de paralelismo: Historia 1

```text
Fase roja (un commit test(PED-15) tras el ⛔ ALTO):
  T007+T008 tests/unit/test_auth_service.py         next seguro, sesión limpia
  T009      tests/integration/test_login_flow.py     entrar y volver a la página pedida
  T010      tests/integration/test_session_cookie.py HttpOnly, SameSite, Secure
  T011      tests/unit/test_google_identity.py       authlib contra MockTransport
  T012      dobles, log_in, fixtures y esqueletos
Fase verde (secuencial): T013 → T014 → T015 → T016
```

## Estrategia de implementación

1. **MVP desplegable = F1 + F2 + US1 + US2 + US3.** Es el mínimo que protege los datos. US1 sola
   es demostrable en local, pero no se despliega.
2. **US4** completa la spec (cerrar sesión y caducidad). Es P2, pero entra en el mismo PR antes
   del merge: el riesgo aceptado se cierra con la historia completa.
3. **Pulido**: documentación de despliegue y Google Cloud, validación manual y pasos en Render.

Commits esperados por fase: `test(PED-15): …` (tras el ⛔ ALTO) → `feat(PED-15): …` →
`refactor(PED-15): …` (opcional).
