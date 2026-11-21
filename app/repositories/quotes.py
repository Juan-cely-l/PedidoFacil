"""Consultas y persistencia de cotizaciones."""

from sqlmodel import Session, col, select

from app.models.quote import Quote


def save_quote(session: Session, quote: Quote) -> Quote:
    """Guarda la cotización con sus líneas en una transacción y la devuelve con su id."""
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return quote


def get_quote(session: Session, quote_id: int) -> Quote | None:
    """Busca una cotización por id; sus líneas se cargan en orden de posición."""
    return session.get(Quote, quote_id)


def list_quotes(session: Session) -> list[Quote]:
    """Cotizaciones de la más reciente a la más antigua."""
    statement = select(Quote).order_by(col(Quote.created_at).desc(), col(Quote.id).desc())
    return list(session.exec(statement).all())
