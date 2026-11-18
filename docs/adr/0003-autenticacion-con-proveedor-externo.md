# ADR 0003: Autenticación con un proveedor de identidad externo

## Estado

Aceptado, 2026-11-18.

Reemplaza la decisión de autenticación del [ADR 0001](0001-stack-tecnologico.md), que fijaba
`SessionMiddleware` de Starlette + `pwdlib[argon2]` para el login del dueño. El resto del stack
del ADR 0001 y lo agregado en el [ADR 0002](0002-alcance-ampliado-mensajeria-e-inventario.md) se
mantienen. La constitución recoge este cambio en su versión 1.2.0 (principios II, IV y VI).

## Contexto

HU-07 (PED-15) protege con login las rutas de la aplicación. Hasta ahora eso importaba poco: el
2026-11-16 se aceptó que `/productos` quedara público mientras tanto, porque los precios no son
datos sensibles. Pero con ese riesgo se fijó un límite: HU-04 no se despliega a producción sin
login, porque guarda nombre, teléfono y dirección de clientes. El login es, por tanto, lo que
habilita llevar datos personales a producción.

Restricciones que condicionan la decisión:

- **Tiempo**: quedan 11 días hasta la entrega (2026-11-29), para una sola persona.
- **Costo cero**: ninguna opción puede exigir pagos ni trámites empresariales.
- **Pruebas sin red** (constitución, principio II): el login debe poder simularse de forma
  determinista.
- **Un solo usuario**: el dueño del emprendimiento; no hay registro público ni roles.
- **Riesgo ya aceptado**: `/productos` sigue público hasta que este login esté desplegado.

## Opciones consideradas

| Opción | A favor | En contra |
|---|---|---|
| Contraseña local con argon2 (`pwdlib`) | Sin configuración en terceros; ya estaba en el ADR 0001; se prueba sin red de forma directa. | La app custodia una contraseña: hay que construir el alta, el cambio y la recuperación de la contraseña, y frenar los intentos por fuerza bruta. Es más superficie de ataque y más trabajo para el plazo, solo para proteger datos personales con una clave que elige el propio dueño. |
| **Google OAuth 2.0 (OpenID Connect) con `authlib`** | El dueño ya tiene cuenta de Google, con su propia verificación en dos pasos; la app no guarda contraseñas; `authlib` se integra con Starlette; la pantalla de consentimiento en modo Testing admite hasta 100 usuarios sin verificación de Google; costo cero. | Configuración externa en la consola de Google Cloud; iniciar sesión depende de que Google esté disponible; entra una dependencia nueva (`authlib`); el cliente OAuth hay que sustituirlo en las pruebas. |
| GitHub OAuth | Flujo equivalente y configuración sencilla. | El usuario objetivo no tiene cuenta de GitHub: tendría que crearla solo para entrar a su propia aplicación. |
| Proveedor gestionado (Auth0, Clerk) | Pantalla de login, verificación en dos pasos y gestión de usuarios ya resueltas. | Añade un proveedor completo (cuenta, panel, SDK y límites del plan gratuito) para autenticar a una sola persona; más configuración externa y otra pieza que simular en las pruebas. |

## Decisión

Se autentica al dueño con **Google OAuth 2.0 (OpenID Connect) mediante `authlib`**, sobre el
`SessionMiddleware` de Starlette, más una **lista blanca de correos en `OWNER_EMAILS`**:
autenticarse con Google no basta para entrar, el correo verificado tiene que estar en la lista.

Razones:

- El usuario objetivo ya tiene cuenta de Google y no tiene GitHub.
- La aplicación no custodia contraseñas: no hay hashes que proteger ni recuperación de
  contraseña que construir.
- La pantalla de consentimiento en modo Testing admite hasta 100 usuarios y no requiere la
  verificación de la aplicación por parte de Google, así que no hay trámite.
- Un proveedor gestionado añadiría un proveedor completo para autenticar a una persona.

La constitución 1.2.0 fija además que la cookie de sesión es `httponly` y `samesite=lax` (y
`secure` en producción), y que los tokens de OAuth y los `id_token` nunca aparecen en logs ni en
mensajes de error.

## Consecuencias

**Positivas**

- No hay contraseñas en la base de datos ni flujos de recuperación que mantener.
- El dueño entra con la cuenta que ya usa, con la verificación en dos pasos que tenga configurada.
- La lista blanca hace explícito quién puede entrar, aunque cualquiera pueda autenticarse con
  Google.
- Cuando HU-07 esté desplegada, deja de aplicar el riesgo de `/productos` público y HU-04 puede
  llegar a producción.

**Negativas y riesgos**

- **Dependencias**: entra `authlib` y sale `pwdlib`. Se agrega con `uv add` cuando se implemente
  HU-07, justificada en su `plan.md`.
- **Configuración externa**: hay que crear el cliente OAuth y la pantalla de consentimiento en la
  consola de Google Cloud, con URIs de redirección para local
  (`http://localhost:8000/...` o `http://127.0.0.1:8000/...`) y para producción (la URL de
  Render). En modo Testing, el correo del dueño debe estar registrado también como usuario de
  prueba en la consola.
- **Pruebas**: el cliente OAuth se sustituye con `app.dependency_overrides` o
  `httpx.MockTransport`; las pruebas nunca llaman a Google (principio II).
- **Disponibilidad**: si Google no responde, el dueño no puede iniciar sesión; una sesión ya
  abierta sigue funcionando hasta que expire.
- **Segunda dependencia externa del Sprint 2**, junto con la clave de Gemini: las dos requieren
  crear credenciales fuera del repositorio y configurarlas en Render antes de desplegar. Si
  alguna falta o falla, bloquea su historia en producción.
- Cambiar de proveedor de identidad requiere un nuevo ADR y una enmienda de la constitución.
