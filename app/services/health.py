"""Comprobaciones de salud de la aplicación."""

from sqlmodel import Session


def check_database(session: Session) -> bool:
    """Indica si la base de datos responde a una consulta mínima."""
    raise NotImplementedError
