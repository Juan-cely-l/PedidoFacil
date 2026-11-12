# Contrato: health checks

Ambos endpoints son públicos (sin autenticación), solo `GET`, y responden JSON.

## `GET /health/live`

Uso: health check de la plataforma (Render). **No** abre conexión a la base de datos.

**200 OK**

```json
{"status": "ok", "version": "0.1.0", "commit": "a1b2c3d"}
```

## `GET /health`

Uso: verificación del job de despliegue (`.github/workflows/ci.yml`, job `deploy`, que compara
`commit` con el SHA desplegado). Ejecuta `SELECT 1` con un tiempo límite de conexión de 5 s.

**200 OK**: la base respondió.

```json
{"status": "ok", "database": "ok", "version": "0.1.0", "commit": "a1b2c3d"}
```

**503 Service Unavailable**: la base no respondió, falló o superó el tiempo límite.

```json
{"status": "error", "database": "error", "version": "0.1.0", "commit": "a1b2c3d"}
```

## Reglas comunes

- `commit`: primeros 7 caracteres de `RENDER_GIT_COMMIT`, o `"local"` si no está definido.
- Ninguna respuesta incluye cadenas de conexión, credenciales, mensajes de excepción ni trazas.
  El detalle de la falla solo se registra en el log, sin credenciales.

# Contrato: documentación de la API

| Ruta | `local` / `test` | `production` |
|---|---|---|
| `/docs` | 200 | 404 |
| `/redoc` | 200 | 404 |
| `/openapi.json` | 200 | 404 |
