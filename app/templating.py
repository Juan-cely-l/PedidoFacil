"""Plantillas Jinja2 de la aplicación y sus filtros."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def cop(amount: int) -> str:
    """Formatea pesos colombianos: 45000 → «$ 45.000».

    No depende del `locale` del servidor, que en Render no es el colombiano.
    """
    return "$ " + f"{amount:,}".replace(",", ".")


templates.env.filters["cop"] = cop
