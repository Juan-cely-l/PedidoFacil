# Contrato: rutas de acceso y protección

## Rutas públicas (`PUBLIC_PATHS`, única lista; R1)

| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/health` | Sin cambios respecto a PED-11 |
| GET | `/health/live` | Sin cambios respecto a PED-11 |
| GET | `/login?next=<path>&aviso=<código>` | 200 con «Entrar con Google» y el aviso traducido (R11); con sesión válida, 303 a `next` validado o `/productos` |
| GET | `/login/google?next=<path>` | Guarda `next` validado en la sesión y responde 302 a Google (lo arma authlib) |
| GET | `/auth/google/callback` | 303 a `next` o `/productos` si el login es válido y autorizado; si no, 303 a `/login?aviso=no_autorizado\|cancelado\|error` |

## Rutas protegidas

Todas las demás `APIRoute`, presentes y futuras. Sin sesión válida:

| Método | Respuesta |
|---|---|
| GET | `303` a `/login?next=<path y query actuales>` |
| POST y otros | `303` a `/login`, sin ejecutar la acción |

| Método | Ruta | Respuesta |
|---|---|---|
| POST | `/logout` | `session.clear()`, 303 a `/login?aviso=salida`. Solo se invoca desde el formulario de la navegación |
| GET | `/logout` | `405 Method Not Allowed`; la sesión no cambia (research.md R5: con `SameSite=lax`, un `GET` desde otro sitio lleva la cookie) |

## Documentación automática

`/docs`, `/redoc` y `/openapi.json` solo existen en `local` y `test`. En producción responden
`404`, porque no se registran (research.md R13).

## Cookie de sesión

`Set-Cookie: pedidofacil_session=…; path=/; Max-Age=43200; HttpOnly; SameSite=lax` y, en
producción, además `Secure`. Las pruebas verifican cada atributo.

## Avisos de la página de login

| `aviso` | Mensaje |
|---|---|
| `no_autorizado` | «Esta cuenta de Google no tiene acceso a PedidoFácil» |
| `cancelado` | «No se completó el inicio de sesión con Google» |
| `error` | «No se pudo iniciar sesión con Google. Intenta de nuevo» |
| `salida` | «Cerraste sesión» |
| otro | No se muestra nada |

## Correspondencia entre motivos de `LoginFailed` y avisos

| Situación | Motivo | Aviso |
|---|---|---|
| Correo verificado fuera de la lista | `no_autorizado` | `no_autorizado` |
| `email_verified` falso | `no_verificado` | `no_autorizado` |
| El usuario canceló en Google (`error=access_denied`) | `cancelado` | `cancelado` |
| `state` desconocido o ya usado | `state_invalido` | `cancelado` |
| Respuesta sin `id_token` | `sin_id_token` | `error` |
| `id_token` inválido (firma, `nonce`, `aud`, `iss`, `exp`) | `id_token_invalido` | `error` |
| Fallo de red con Google | `red` | `error` |

## Navegación (`base.html`)

Con sesión: «Productos», el nombre o correo del dueño y un formulario `POST /logout` con el botón
«Cerrar sesión». Sin sesión: solo el nombre de la aplicación.
