"""Dobles de prueba compartidos."""

from typing import Any, NoReturn

from sqlalchemy.exc import OperationalError
from sqlmodel import Session

# Mensaje con credenciales, como el que daría el controlador real: nunca debe filtrarse.
LEAKY_DB_ERROR = "no se pudo conectar a postgresql://usuario:clave@host/db"


class FailingSession(Session):
    """Sesión que simula una base de datos caída: toda consulta lanza OperationalError."""

    def exec(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise OperationalError("SELECT 1", {}, Exception(LEAKY_DB_ERROR))

    def execute(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        raise OperationalError("SELECT 1", {}, Exception(LEAKY_DB_ERROR))
