# Contrato: servicio de cotización (lo que usará HU-20)

`app/services/quotes.py`. No importa FastAPI, Starlette, Jinja2 ni `app.config` (RD-1,
research R8). Lo llaman igual el router web y el webhook de Telegram de HU-20.

```text
async quote_message(
    session: Session,
    message: str,
    *,
    extractor: Agent[None, QuoteExtraction] | None,   # None = IA desactivada (R12)
    timeout_seconds: float,                           # 0 < t ≤ 15 (principio V)
    today: date,                                      # día actual en America/Bogota
    now: datetime,                                    # UTC, para created_at
) -> Quote
```

- **Errores de dominio**, que se lanzan **antes** de llamar a la IA:
  - `EmptyMessageError` y `MessageTooLongError`: mensaje vacío o de más de 2000 caracteres.
  - `NothingToQuoteError`: `list_quotable_items` devuelve una lista vacía.
- **Nunca lanza por fallas de la IA**: devuelve siempre un `Quote` guardado en `borrador`, con su
  `ai_outcome` (research R4).
- **Precios**: todos salen de `list_quotable_items(session)`, leído **una vez** por llamada; el
  mismo listado se usa para armar las instrucciones y para validar la salida (R5 y R6).

Conversión pura, sin base de datos; la usan `quote_message`, las pruebas del banco y el script de
medición (research R5 y R14):

```text
build_lines(extraction: QuoteExtraction, items: list[QuotableItem]) -> list[LineDraft]
```

Operaciones de edición, síncronas y cada una en su propia transacción:

```text
get_quote(session, quote_id) -> Quote                      # QuoteNotFoundError
list_quotes(session) -> list[Quote]                        # más reciente primero
add_line(session, quote_id, data: LineInput) -> QuoteLine  # ItemNotQuotableError
update_line(session, quote_id, line_id, data: LineInput) -> QuoteLine
remove_line(session, quote_id, line_id) -> None            # QuoteLineNotFoundError
update_delivery(session, quote_id, data: DeliveryInput) -> Quote
quote_total(quote) -> int                                  # suma de subtotales «lista»
pending_count(quote) -> int
```

`app/services/quote_ai.py`, también sin dependencias de la web:

```text
build_quote_agent(*, provider: Literal["fake","gemini"], api_key: str | None,
                  model_name: str, fallback_model_name: str | None,
                  timeout_seconds: float) -> Agent[None, QuoteExtraction] | None
render_catalog_prompt(items: list[QuotableItem], message: str) -> str  # sin precios
resolve_delivery_date(expr: DateExpression | None, today: date) -> tuple[date | None, bool]
```
