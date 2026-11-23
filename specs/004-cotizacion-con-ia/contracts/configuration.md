# Contrato: configuración nueva

Variables de entorno que se agregan a `Settings`. Se documentan en `.env.example` y en
`docs/despliegue.md`.

| Variable | Tipo y valor por defecto | Validación | Producción |
|---|---|---|---|
| `AI_PROVIDER` | ya existe: `fake` o `gemini` | Sin cambios. | `gemini` con esta historia |
| `GEMINI_API_KEY` | ya existe | Obligatoria con `AI_PROVIDER=gemini`; sin cambios. | En Render |
| `GEMINI_MODEL` | texto; `gemini-3.5-flash-lite` | No en blanco (solo espacios impide arrancar). Vacía cuenta como ausente. | Opcional: se cambia según la medición (research R2) |
| `GEMINI_FALLBACK_MODEL` | texto; sin respaldo por defecto (desde la medición del 2026-11-23, research R2) | `ninguno` desactiva el respaldo; vacía cuenta como ausente (valor por defecto), como toda la configuración; no puede ser igual a `GEMINI_MODEL`. | Opcional |
| `AI_TIMEOUT_SECONDS` | número; `10` | Mayor que 0 y **≤ 15**, el tope del principio V. Fuera de ese rango, la app no arranca, en cualquier ambiente. | Opcional |

- Los nombres de los modelos no son secretos: el log de arranque los menciona, junto con el tiempo
  de espera. La clave nunca aparece.
- Con `AI_PROVIDER=fake` se ignoran las tres variables nuevas (research R12).
- En pruebas, `Settings` no lee `.env` (como hasta ahora) y el servicio recibe el tiempo de espera
  como parámetro.
