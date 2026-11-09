"""Configuración de la aplicación leída desde variables de entorno (o un archivo .env local)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores configurables. Nunca se guardan secretos en el código ni en el repositorio."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PedidoFácil"
    environment: Literal["local", "test", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Render define RENDER_GIT_COMMIT en cada despliegue: permite saber qué commit está corriendo.
    git_commit: str = Field(default="local", validation_alias="RENDER_GIT_COMMIT")


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración, leída una sola vez por proceso."""
    return Settings()
