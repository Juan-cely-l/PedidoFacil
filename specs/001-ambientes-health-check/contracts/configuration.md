# Contrato: variables de entorno

Es la interfaz entre la aplicación y quien la despliega. `.env.example` DEBE listarlas todas,
comentadas o con valores no secretos (FR-016). Detalle de tipos y defaults en
[../data-model.md](../data-model.md).

| Variable | Admitidos | Obligatoria en `production` | Notas |
|---|---|---|---|
| `ENVIRONMENT` | `test`, `local`, `production` | — (por defecto `production`) | `.env.example` trae `ENVIRONMENT=local` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | No | Por defecto según ambiente |
| `DATABASE_URL` | URL `postgresql://…` (prod.), `sqlite:///…` (local) | Sí, PostgreSQL | Neon: usar la URL con `sslmode=require` |
| `SECRET_KEY` | texto ≥ 32 caracteres | Sí | Generar con `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AI_PROVIDER` | `fake`, `gemini` | No (por defecto `gemini`) | `fake` en producción deja un log WARNING |
| `GEMINI_API_KEY` | texto | Sí, si `AI_PROVIDER=gemini` | — |
| `RENDER_GIT_COMMIT` | SHA | No | Lo define Render; no va en `.env.example` como obligatoria |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `OWNER_TELEGRAM_CHAT_ID` | — | No (HU-19/HU-20) | Se conservan comentadas |

## Errores de arranque

Ejemplo del mensaje con `ENVIRONMENT` sin definir y sin `.env`:

```text
Configuración inválida para ENVIRONMENT=production:
- DATABASE_URL: falta (debe ser una URL de PostgreSQL)
- SECRET_KEY: falta (mínimo 32 caracteres)
- GEMINI_API_KEY: falta (obligatoria con AI_PROVIDER=gemini)
Para desarrollo local copia .env.example a .env (ENVIRONMENT=local)
```

El texto exacto puede variar; lo obligatorio es: nombrar cada variable, el motivo, ningún valor y
la sugerencia final.
