"""Plantillas Jinja2 de la aplicación y sus filtros."""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

COLOMBIA = ZoneInfo("America/Bogota")

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def cop(amount: int) -> str:
    """Formatea pesos colombianos: 45000 → «$ 45.000».

    No depende del `locale` del servidor, que en Render no es el colombiano.
    """
    return "$ " + f"{amount:,}".replace(",", ".")


def colombia(moment: datetime.datetime) -> str:
    """Fecha y hora en Colombia: «20/11/2026 22:30».

    SQLite no guarda la zona horaria: un valor sin zona se toma como UTC, que es como se guarda.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.UTC)
    return moment.astimezone(COLOMBIA).strftime("%d/%m/%Y %H:%M")


templates.env.filters["cop"] = cop
templates.env.filters["colombia"] = colombia
