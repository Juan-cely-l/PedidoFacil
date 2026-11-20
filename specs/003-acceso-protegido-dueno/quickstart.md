# Validación rápida: PED-15 · HU-07 Acceso protegido del dueño

## Pruebas automáticas (sin Google)

```bash
uv run pytest && uv run ruff check . && uv run mypy
```

Qué debe quedar en verde, entre otras pruebas:

- la cobertura de rutas: ninguna ruta de gestión queda accesible sin sesión (R2);
- el flujo con el proveedor falso: login, rechazo, cancelación, logout y caducidad con
  `time-machine`;
- authlib real contra un Google simulado con `httpx.MockTransport`: `state`, `nonce` y falta de
  `id_token` (R7);
- los atributos de la cookie, en test y en producción;
- `GET /logout` responde 405 y no cierra la sesión.

La prueba de cobertura de rutas corre sobre la app configurada como producción, donde no existen
`/docs`, `/redoc` ni `/openapi.json`.

## Preparación en Google Cloud (una sola vez)

1. Crear un proyecto y configurar la pantalla de consentimiento: externa, en modo Testing, con el
   correo del dueño como usuario de prueba.
2. Crear un ID de cliente de OAuth de tipo «Aplicación web» y registrar las URIs de research.md
   R10.
3. Copiar el ID y el secreto en `.env` (local) y en Render → Environment (producción), junto con
   `OWNER_EMAILS` y, en producción, `PUBLIC_BASE_URL=https://pedidofacil-6nky.onrender.com`.

## Recorrido manual en local (`uv run fastapi dev app/main.py`, abrir http://127.0.0.1:8000)

1. Abrir `/productos` sin sesión → redirige a `/login?next=/productos`.
2. «Entrar con Google» con el correo del dueño → vuelve a `/productos` y la navegación muestra
   su nombre.
3. Recargar tras reiniciar el servidor, con `SECRET_KEY` fija en `.env` → la sesión sigue.
4. «Cerrar sesión» → `/login` con «Cerraste sesión»; `/productos` vuelve a pedir login.
5. Entrar con otra cuenta de Google, que también debe estar registrada como usuario de prueba en
   la consola → «Esta cuenta de Google no tiene acceso a PedidoFácil».
6. `/health` y `/health/live` responden sin sesión.
7. En las herramientas del navegador, la cookie `pedidofacil_session` aparece como `HttpOnly` y
   `SameSite=Lax`.

## Producción (tras el merge)

- `/health` sigue en 200 y Render no reinicia el servicio.
- `https://pedidofacil-6nky.onrender.com/productos` exige login, que funciona con la URI
  `https://pedidofacil-6nky.onrender.com/auth/google/callback`.
- La cookie es `Secure`.
- `https://pedidofacil-6nky.onrender.com/docs` y `/openapi.json` responden 404.
