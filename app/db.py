"""Acceso a la base de datos: motor de SQLModel y sesión por petición."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

_POSTGRES_SCHEMES = ("postgresql", "postgres")
_POSTGRES_DRIVER = "postgresql+psycopg"
# Si la base no responde, /health devuelve 503 en lugar de quedarse esperando.
_CONNECT_TIMEOUT_SECONDS = 5


def build_engine(url: str) -> Engine:
    """Crea el motor de base de datos para la URL dada, sin abrir conexiones."""
    if url.startswith("sqlite"):
        # TestClient atiende las peticiones en otro hilo; SQLite debe permitirlo.
        sqlite_args = {"check_same_thread": False}
        if make_url(url).database in (None, "", ":memory:"):
            # Una sola conexión compartida: si no, cada conexión vería una base vacía distinta.
            return create_engine(url, connect_args=sqlite_args, poolclass=StaticPool)
        return create_engine(url, connect_args=sqlite_args)

    return create_engine(
        _with_psycopg_driver(url),
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
        # Neon cierra las conexiones al suspenderse: se verifican antes de usarlas.
        pool_pre_ping=True,
    )


def _with_psycopg_driver(url: str) -> str:
    """Usa psycopg 3: Neon entrega `postgresql://`, que SQLAlchemy asociaría a psycopg2."""
    scheme, rest = url.split("://", 1)
    if scheme in _POSTGRES_SCHEMES:
        return f"{_POSTGRES_DRIVER}://{rest}"
    return url


def get_session(request: Request) -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión sobre el motor de la app y la cierra al final."""
    engine: Engine = request.app.state.engine
    with Session(engine) as session:
        yield session
