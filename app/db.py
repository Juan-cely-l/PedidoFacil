"""Acceso a la base de datos: motor de SQLModel y sesión por petición."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine
from sqlmodel import Session


def build_engine(url: str) -> Engine:
    """Crea el motor de base de datos para la URL dada, sin abrir conexiones."""
    raise NotImplementedError


def get_session(request: Request) -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión sobre el motor de la app y la cierra al final."""
    raise NotImplementedError
