"""Configuración de la aplicación leída desde variables de entorno (o un archivo .env local)."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fuera de producción no hace falta definir DATABASE_URL: se usa SQLite.
_DEFAULT_DATABASE_URLS = {"test": "sqlite://", "local": "sqlite:///./pedidofacil.db"}


class Settings(BaseSettings):
    """Valores configurables. Nunca se guardan secretos en el código ni en el repositorio."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PedidoFácil"
    environment: Literal["test", "local", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Render define RENDER_GIT_COMMIT en cada despliegue: permite saber qué commit está corriendo.
    git_commit: str = Field(default="local", validation_alias="RENDER_GIT_COMMIT")
    database_url: SecretStr | None = None

    @model_validator(mode="after")
    def _apply_environment_defaults(self) -> Self:
        """Completa los valores que dependen del ambiente cuando no se definieron."""
        if self.database_url is None and self.environment in _DEFAULT_DATABASE_URLS:
            self.database_url = SecretStr(_DEFAULT_DATABASE_URLS[self.environment])
        return self


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración, leída una sola vez por proceso."""
    return Settings()
