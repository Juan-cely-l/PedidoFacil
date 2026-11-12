# Modelo de datos (Fase 1): PED-11 · HU-03 Ambientes y health check

Esta historia no crea tablas (HU-15). Las dos «entidades» son estructuras en memoria.

## Settings (`app/config.py`)

Configuración del proceso, leída de variables de entorno y, salvo en `test`, de `.env`.

| Campo | Variable | Tipo | Por defecto | Validación |
|---|---|---|---|---|
| `environment` | `ENVIRONMENT` | `Literal["test", "local", "production"]` | `"production"` | Otro valor → error con los admitidos |
| `log_level` | `LOG_LEVEL` | `Literal["DEBUG", "INFO", "WARNING", "ERROR"] \| None` | DEBUG (`local`), INFO (`test`, `production`) | — |
| `database_url` | `DATABASE_URL` | `SecretStr \| None` | `sqlite:///./pedidofacil.db` (`local`), `sqlite://` (`test`) | `production`: obligatorio y PostgreSQL |
| `secret_key` | `SECRET_KEY` | `SecretStr \| None` | `secrets.token_urlsafe(48)` generado al construir `Settings` (`local`, `test`); nunca un valor escrito en el código | `production`: obligatorio, ≥ 32 caracteres |
| `ai_provider` | `AI_PROVIDER` | `Literal["fake", "gemini"] \| None` | `fake` (`local`, `test`), `gemini` (`production`) | Otro valor → error con los admitidos |
| `gemini_api_key` | `GEMINI_API_KEY` | `SecretStr \| None` | `None` | Obligatorio si `production` y `ai_provider == "gemini"` |
| `git_commit` | `RENDER_GIT_COMMIT` | `str` | `"local"` | — |

**Reglas**

- Una variable definida pero vacía cuenta como ausente.
- En `production`, el validador acumula todos los errores y lanza uno solo; el mensaje nombra cada
  variable y su motivo, no incluye valores y termina con «Para desarrollo local copia
  .env.example a .env (ENVIRONMENT=local)».
- `hide_input_in_errors=True`: los errores de Pydantic no muestran los datos de entrada.
- Propiedades derivadas: `docs_enabled` (`environment != "production"`) y `short_commit`
  (`git_commit[:7]`).
- Efecto al arrancar: si `environment == "production"` y `ai_provider == "fake"`, se registra un
  log WARNING.
- El nombre de la aplicación no es configurable: es la constante `APP_NAME = "PedidoFácil"` en
  `app/__init__.py`, junto a `__version__`.

**Transiciones**: ninguna; la configuración se construye una vez por proceso (`get_settings()` en
caché) y es inmutable.

## Estado de la aplicación (`app.state`)

Fuente única de configuración en tiempo de ejecución, fijada por `create_app(settings)`:

| Atributo | Tipo | Origen |
|---|---|---|
| `app.state.settings` | `Settings` | el argumento de `create_app`, o `get_settings()` si no se pasa |
| `app.state.engine` | `Engine` | `build_engine(settings.database_url)`; perezoso, no conecta al crearse |

`get_session` y el router de health los leen de `request.app.state` mediante `Depends`; ningún
código fuera de `create_app` llama a `get_settings()`.

## HealthStatus (respuesta de `/health` y `/health/live`)

| Campo | Tipo | Valores | Presente en |
|---|---|---|---|
| `status` | `str` | `"ok"` \| `"error"` | ambos |
| `database` | `str` | `"ok"` \| `"error"` | solo `/health` |
| `version` | `str` | `app.__version__` | ambos |
| `commit` | `str` | 7 caracteres o `"local"` | ambos |

`status` es `"error"` exactamente cuando `database` es `"error"`; el código HTTP es 200 o 503 en
consecuencia. Contrato completo: [contracts/health.md](contracts/health.md).
