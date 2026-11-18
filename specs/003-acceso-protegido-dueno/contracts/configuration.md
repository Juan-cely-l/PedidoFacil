# Contrato: configuración del login

| Variable | Tipo | Producción | Local | Pruebas |
|---|---|---|---|---|
| `GOOGLE_CLIENT_ID` | texto | Obligatoria | Opcional; sin ella, `/login/google` responde con el aviso `error` | `test-client-id` |
| `GOOGLE_CLIENT_SECRET` | secreto | Obligatoria | Igual que arriba | `test-client-secret` |
| `OWNER_EMAILS` | correos separados por comas | Obligatoria, al menos uno | Opcional | `dueno@example.com` |
| `PUBLIC_BASE_URL` | URL | Obligatoria y `https://`: `https://pedidofacil-6nky.onrender.com`; si falta, `RENDER_EXTERNAL_URL` | `http://127.0.0.1:8000` | `http://testserver` |

- **Validación en producción**: sin estas variables la app no arranca, y el error nombra cada una
  sin mostrar su valor.
- **`.env.example`**: documenta las cuatro sin valores reales (lo verifica
  `tests/unit/test_env_example.py`).
- **`RENDER_EXTERNAL_URL`**: la define Render y se trata como `RENDER_GIT_COMMIT`, como variable
  de plataforma.
- **URI de vuelta**: `{PUBLIC_BASE_URL}/auth/google/callback`; en producción,
  `https://pedidofacil-6nky.onrender.com/auth/google/callback`. Las URIs que hay que registrar en
  Google Cloud están en research.md R10.
- **`SECRET_KEY`**: sigue igual. Rotarla invalida todas las sesiones (research.md R8).
