# Plan de implementación: PED-15 · HU-07 Acceso protegido del dueño

**Rama**: `feature/PED-15-acceso-protegido` | **Fecha**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Entrada**: especificación de `specs/003-acceso-protegido-dueno/spec.md` y el diseño de
seguridad pedido por el autor el 2026-11-18.

## Resumen

Login del dueño con Google OAuth 2.0 (OIDC) mediante `authlib`, sobre un `SessionMiddleware` de
Starlette que esta historia agrega, porque hoy solo existe `SECRET_KEY`. Enfoque:

- **Denegar por defecto**: `require_owner` como dependencia de toda la app, con una única lista
  explícita `PUBLIC_PATHS`, más una prueba que recorre `app.routes` de la app de producción y falla
  si alguna ruta queda fuera del mecanismo, sin excepciones (R1, R2).
- **Documentación automática apagada en producción**: ya lo está desde PED-11; aquí se ratifica,
  porque la prueba de rutas depende de ello (R13).
- **Cierre de sesión solo por `POST`** desde un formulario. Con `SameSite=lax`, un `GET` desde
  otro sitio llevaría la cookie y podría cerrar la sesión; `GET /logout` responde 405 (R5).
- **Proveedor sustituible**: `IdentityProvider` es la interfaz; `GoogleIdentityProvider` la
  implementa con authlib, y el proveedor falso se inyecta con `dependency_overrides` (R3).
- **authlib valida `state` y `nonce`**, verificado en su código. Hay una condición: sin
  `id_token` no valida nada, así que la app exige `userinfo`. Se prueba contra un Google simulado
  con `httpx.MockTransport` (R7).
- **Destino de retorno**: solo paths propios; se rechazan las URL absolutas, `//` y `\` (R4).
- **Sesión**: se limpia al entrar y se vacía al salir; dura 12 h desde el login, con caducidad
  absoluta, y la cookie es `HttpOnly`, `SameSite=lax` y `Secure` en producción (R5).
- **Lista blanca** `OWNER_EMAILS`, normalizada y revisada en cada petición (R6).

Decisiones en [research.md](research.md).

## Contexto técnico

**Lenguaje/versión**: Python 3.12 (uv)

**Dependencias principales**: FastAPI, SQLModel y Jinja2 (existentes); **nuevas**: `authlib` y
`itsdangerous`; **nueva de desarrollo**: `time-machine` (R12)

**Almacenamiento**: sin tablas nuevas. La sesión vive en una cookie firmada y la lista blanca en
la configuración ([data-model.md](data-model.md)).

**Pruebas**:
- `tests/unit`: destino de retorno, correos, caducidad con `time-machine`, configuración, y
  `GoogleIdentityProvider` contra `httpx.MockTransport`.
- `tests/integration`: flujo completo con el proveedor falso, cobertura de rutas y atributos de
  la cookie.

**Plataforma**: Render (sin cambios en Build ni Start Command; variables nuevas en Environment)

**Tipo de proyecto**: servicio web (monolito FastAPI en capas)

**Metas de rendimiento**: `require_owner` no consulta la base, solo la cookie y la configuración
en memoria; `/health` no cambia.

**Restricciones**:
- ningún token en logs, errores ni sesión;
- sin red en las pruebas;
- `mypy --strict`;
- cobertura ≥ 80 % con ramas.

**Escala/alcance**: 1 dueño (lista de 1 a pocos correos); ~6 archivos de código, 2 plantillas y
~6 archivos de prueba.

## Verificación de la constitución (1.2.0)

*Puerta: antes de la Fase 0 y de nuevo tras la Fase 1.*

| Principio | Cumplimiento | Estado |
|---|---|---|
| I. TDD | Cada tarea irá precedida de su prueba; commits `test` → `feat` → `refactor` | ✅ |
| II. Pruebas deterministas | Ninguna prueba llama a Google: proveedor falso con `dependency_overrides` y authlib real contra `httpx.MockTransport` (R3, R7); caducidad con `time-machine`; SQLite en memoria | ✅ |
| III. Calidad | Sin cambios en la configuración de las herramientas | ✅ |
| IV. Stack y YAGNI | Google OAuth 2.0 (OIDC) con `authlib` sobre `SessionMiddleware`, sin contraseñas; `itsdangerous` y `time-machine` justificadas (R12); sin tablas; la duración de la sesión es una constante, sin variable de entorno; las capas son router → servicio, y el proveedor va detrás de una interfaz | ✅ |
| V. La IA asiste | No aplica | ✅ |
| VI. Seguridad y privacidad | Documentación de la API apagada en producción (R13); logout solo por `POST` (R5); lista blanca `OWNER_EMAILS` revisada en cada petición (R6); cookie `HttpOnly`, `SameSite=lax` y `Secure` en producción, probada en la cabecera (R5); tokens fuera de logs, errores y sesión (R7, R11); sin correos en logs; destino de retorno validado (R4); sesión limpiada al entrar y al salir (R5) | ✅ |
| VII. Trazabilidad | Rama `feature/PED-15-…`; commits `tipo(PED-15): …` | ✅ |

**Tras el diseño (Fase 1)**: sin cambios; ninguna violación.

## Estructura del proyecto

### Documentación (esta funcionalidad)

```text
specs/003-acceso-protegido-dueno/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── auth-routes.md
│   └── configuration.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Código fuente

```text
app/
├── config.py               # MODIFICAR: google_client_id, google_client_secret, owner_emails
│                           #   (frozenset normalizado), public_base_url (o RENDER_EXTERNAL_URL);
│                           #   validación de producción
├── main.py                 # MODIFICAR: SessionMiddleware (R5), dependencia global require_owner,
│                           #   manejador de LoginRequired, proveedor en app.state, router de auth
├── security.py             # NUEVO: PUBLIC_PATHS, LoginRequired, require_owner, SESSION_MAX_AGE_SECONDS
├── services/
│   ├── auth.py             # NUEVO: normalize_email, safe_next_path, start_session, end_session,
│   │                       #   current_owner (caducidad y lista blanca)
│   └── identity.py         # NUEVO: VerifiedIdentity, LoginFailed, IdentityProvider (Protocol),
│                           #   GoogleIdentityProvider (authlib), get_identity_provider
├── routers/
│   └── auth.py             # NUEVO: GET /login, GET /login/google, GET /auth/google/callback, POST /logout
└── templates/
    ├── base.html           # MODIFICAR: dueño conectado y botón «Cerrar sesión»
    └── auth/login.html     # NUEVO

tests/
├── conftest.py             # MODIFICAR: FakeIdentityProvider; `client` pasa a tener sesión iniciada
│                           #   (las pruebas del catálogo no se tocan); nueva fixture `anonymous_client`
├── doubles.py              # MODIFICAR: FakeIdentityProvider
├── unit/
│   ├── test_auth_service.py       # NUEVO: next seguro, correos, start/end_session, caducidad
│   ├── test_google_identity.py    # NUEVO: authlib real contra httpx.MockTransport (state, nonce, sin id_token)
│   ├── test_config.py             # AMPLIAR: variables nuevas y validación de producción
│   └── test_env_example.py        # (sin cambios de código; .env.example se amplía)
└── integration/
    ├── test_login_flow.py         # NUEVO: entrar, rechazos, next, logout, caducidad, quitar de la lista
    ├── test_route_protection.py   # NUEVO: recorrido de app.routes de la app de producción, sin excepciones (R2)
    └── test_session_cookie.py     # NUEVO: HttpOnly, SameSite=lax, Secure en producción

.env.example                # MODIFICAR: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OWNER_EMAILS, PUBLIC_BASE_URL
docs/despliegue.md          # MODIFICAR: variables nuevas, URIs de Google, rotación de SECRET_KEY,
                            #   cierre del riesgo de /productos público
```

**Decisión de estructura**:
- `require_owner` va en `app/security.py` y no en un router, porque se registra en la app (R1).
- La lógica pura está en `app/services/auth.py`, sin HTTP, y se prueba con pruebas unitarias.
- La integración externa queda aislada en `app/services/identity.py`.

## Notas para `/speckit-tasks`

- **Orden**:
  1. Dependencias y configuración.
  2. Lógica pura (`safe_next_path`, correos, sesión y caducidad).
  3. `SessionMiddleware` + `require_owner` + prueba de cobertura de rutas.
  4. Router de auth con el proveedor falso.
  5. `GoogleIdentityProvider` contra `MockTransport`.
  6. Navegación y documentación.
- **Fixture `client`**: hoy la usan todas las pruebas del catálogo. Pasa a hacer login con el
  proveedor falso (`/login/google` → callback), para que esas pruebas sigan sin tocarse. El hook
  `guard_files.py` pedirá confirmación al editar `tests/conftest.py`.
- **Prueba de cobertura de rutas**: `create_app(production_settings)` (la fixture ya existe en
  `tests/conftest.py`; se le agregan las variables nuevas de Google y `OWNER_EMAILS`), con
  `dependency_overrides` para `get_session` (`FailingSession`) y `get_identity_provider` (el
  proveedor falso). Cero excepciones para la documentación.
- **Logout**: probar que `GET /logout` → 405 y que la sesión sigue valiendo después; y que
  `POST /logout` la vacía.
- **Casos de `safe_next_path`**: `"/productos"` → igual; `"/productos?x=1"` → igual; `None`,
  `""`, `"productos"`, `"//evil.com"`, `"/\\evil.com"`, `"https://evil.com"`,
  `"/login"`, `"/logout"`, `"/auth/google/callback"` y `"/x\n"` → `None`.
- **Prueba de tokens fuera de logs**: el proveedor falso y el `MockTransport` devuelven tokens
  centinela (`"TOKEN-CENTINELA-…"`). La prueba verifica con `caplog` y en el cuerpo de las
  respuestas que no aparecen, y que la sesión decodificada no los contiene.
- **Revisar la lista blanca en cada petición**: la prueba crea la sesión con `OWNER_EMAILS={a}`,
  reconstruye la app con `OWNER_EMAILS={b}` y la misma `SECRET_KEY`, reutiliza la cookie y espera
  la redirección al login.
- **Sobrevivir a un reinicio**: misma técnica, con la misma `SECRET_KEY` y `OWNER_EMAILS`; la
  cookie sigue valiendo en la app nueva. Con otra `SECRET_KEY`, deja de valer: documenta R8.

## Riesgos y pasos manuales

- **Configuración en Google Cloud** (manual, del autor): pantalla de consentimiento en modo
  Testing con el correo del dueño como usuario de prueba, ID de cliente web y URIs de
  redirección (research.md R10). Sin esto, el login falla en local y en producción, aunque las
  pruebas pasen.
- **Variables en Render antes del merge**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `OWNER_EMAILS` y `PUBLIC_BASE_URL=https://pedidofacil-6nky.onrender.com`. Sin ellas, la app no arranca en producción (FR-012),
  por diseño. En Google Cloud hay que registrar la URI `https://pedidofacil-6nky.onrender.com/auth/google/callback`
  (research.md R10).
- **Rotación de `SECRET_KEY`**: invalida todas las sesiones y los logins en curso; es el
  mecanismo para cerrar todas las sesiones (research.md R8). Se documenta en
  `docs/despliegue.md`.
- **Cookie no revocable**: una cookie robada vale hasta 12 h. Mitigación: `HttpOnly`,
  `SameSite=lax`, `Secure` y rotar `SECRET_KEY` ante sospecha.
- **Cierre del riesgo aceptado el 2026-11-16**: al desplegar esta historia, `/productos` deja de
  ser público y se levanta el límite que impedía desplegar HU-04. Hay que actualizar la tabla de
  riesgos de `docs/despliegue.md`.
- **Dos dependencias externas en el Sprint 2** (Google y Gemini), registradas en el ADR 0003.

## Seguimiento de complejidad

Sin violaciones que justificar.
