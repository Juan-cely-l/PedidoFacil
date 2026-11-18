# Modelo de datos: PED-15 · HU-07 Acceso protegido del dueño

Esta historia **no crea tablas ni migraciones**. Lo que se guarda vive en la cookie de sesión
firmada y en la configuración.

## Sesión del dueño (cookie `pedidofacil_session`, firmada con `SECRET_KEY`)

```text
session = {
  "owner": {
    "email": "dueno@gmail.com",     # normalizado (strip + casefold)
    "name": "Nombre en Google",     # solo para mostrar en la navegación
    "login_at": 1795000000          # segundos desde la época, al aceptar el login
  }
}
```

| Clave | Cuándo existe | Notas |
|---|---|---|
| `owner` | Tras un login aceptado | Se escribe después de `session.clear()` (R5). |
| `login_next` | Entre `/login/google` y el callback | El destino ya validado (R4); se descarta al entrar. |
| `_state_google_<state>` | Entre `/login/google` y el callback | Lo escribe y borra authlib (R7). |

- **Nunca se guardan**: tokens de acceso, `id_token`, refresh tokens ni contraseñas.
- **Válida si**:
  - la firma es correcta;
  - `now - login_at < SESSION_MAX_AGE_SECONDS` (12 h);
  - `owner.email` está en `OWNER_EMAILS` en el momento de la petición.

## VerifiedIdentity (valor en memoria, no se persiste)

`email: str`, `email_verified: bool`, `name: str`. La construye `IdentityProvider.complete_login`
a partir del `userinfo` del `id_token` ya validado.

## Lista blanca

`OWNER_EMAILS`: correos separados por comas. Se leen en `Settings` como `frozenset[str]`
normalizado. No es una tabla: cambiarla requiere un redeploy.

## Estados

```text
anónimo ──/login/google──▶ en Google ──callback válido + autorizado──▶ con sesión
                                │
                                └── rechazo / cancelación / error ──▶ anónimo (login?aviso=…)
con sesión ──POST /logout──▶ anónimo (session.clear())
con sesión ──12 h desde login_at, o correo fuera de la lista──▶ anónimo (session.clear() + login)
```
