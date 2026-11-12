"""Comprobaciones de salud de la aplicación."""

import logging

from sqlalchemy import literal
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

logger = logging.getLogger("pedidofacil.health")


def check_database(session: Session) -> bool:
    """Indica si la base de datos responde a una consulta mínima."""
    try:
        # SELECT 1: la consulta más barata que obliga a abrir una conexión real.
        session.exec(select(literal(1))).one()
    except SQLAlchemyError as error:
        # Solo el tipo de error: el mensaje del controlador puede incluir la URL con credenciales.
        logger.warning("La base de datos no respondió (%s)", type(error).__name__)
        return False
    return True
