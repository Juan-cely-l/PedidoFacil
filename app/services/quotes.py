"""Servicio de cotización: del mensaje del cliente a un borrador con precios del catálogo.

La IA interpreta y el código calcula (principio V): los precios salen solo de
`list_quotable_items`. No importa FastAPI, Starlette, Jinja2, `app.config` ni `app.db`, para que
la ruta web y el webhook de Telegram (HU-20) llamen a las mismas funciones (RD-1, research R8).
"""

from pydantic import BaseModel

from app.models.quote import LineStatus, ReviewReason


class LineDraft(BaseModel):
    """Una línea calculada por el código a partir de la extracción, antes de guardarse.

    `label` y `unit_price` salen del `QuotableItem` del catálogo; son `None` si la línea está
    «Por revisar» (data-model.md).
    """

    customer_text: str | None
    product_id: int | None
    variant_id: int | None
    quantity: int | None
    quantity_assumed: bool
    status: LineStatus
    review_reason: ReviewReason | None
    label: str | None
    unit_price: int | None
