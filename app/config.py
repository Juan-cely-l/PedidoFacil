"""Configuración de la aplicación leída desde variables de entorno (o un archivo .env local)."""

import secrets
from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fuera de producción no hace falta definir DATABASE_URL: se usa SQLite.
_DEFAULT_DATABASE_URLS = {"test": "sqlite://", "local": "sqlite:///./pedidofacil.db"}
_POSTGRES_SCHEMES = ("postgresql", "postgres")
_MIN_SECRET_KEY_LENGTH = 32
_LOCAL_HINT = "Para desarrollo local copia .env.example a .env (ENVIRONMENT=local)"


class Settings(BaseSettings):
    """Valores configurables. Nunca se guardan secretos en el código ni en el repositorio."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Una variable definida pero vacía cuenta como ausente.
        env_ignore_empty=True,
        # Los errores de validación no repiten los valores recibidos (pueden ser secretos).
        hide_input_in_errors=True,
    )

    # Por defecto, el ambiente más estricto: local y test se declaran explícitamente.
    environment: Literal["test", "local", "production"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Render define RENDER_GIT_COMMIT en cada despliegue: permite saber qué commit está corriendo.
    git_commit: str = Field(default="local", validation_alias="RENDER_GIT_COMMIT")
    database_url: SecretStr | None = None
    secret_key: SecretStr | None = None
    ai_provider: Literal["fake", "gemini"] | None = None
    gemini_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _apply_environment_rules(self) -> Self:
        """Completa los valores por ambiente y, en producción, exige las variables obligatorias."""
        if self.environment == "production":
            if self.ai_provider is None:
                self.ai_provider = "gemini"
            problems = self._production_problems()
            if problems:
                # Un único error con todas las variables, para corregirlas de una vez.
                lines = "\n".join(f"- {problem}" for problem in problems)
                message = f"Configuración inválida para ENVIRONMENT=production:\n{lines}\n"
                raise ValueError(message + _LOCAL_HINT)
            return self

        if self.ai_provider is None:
            self.ai_provider = "fake"
        if self.database_url is None:
            self.database_url = SecretStr(_DEFAULT_DATABASE_URLS[self.environment])
        if self.secret_key is None:
            # Clave aleatoria por proceso: nunca un valor fijo escrito en el código.
            self.secret_key = SecretStr(secrets.token_urlsafe(48))
        return self

    def _production_problems(self) -> list[str]:
        """Lista cada variable de producción ausente o inválida, sin incluir su valor."""
        problems: list[str] = []
        if self.database_url is None:
            problems.append("DATABASE_URL: falta (debe ser una URL de PostgreSQL)")
        elif not _is_postgres_url(self.database_url.get_secret_value()):
            problems.append("DATABASE_URL: debe ser una URL de PostgreSQL")
        if self.secret_key is None:
            problems.append(f"SECRET_KEY: falta (mínimo {_MIN_SECRET_KEY_LENGTH} caracteres)")
        elif len(self.secret_key.get_secret_value()) < _MIN_SECRET_KEY_LENGTH:
            problems.append(f"SECRET_KEY: debe tener al menos {_MIN_SECRET_KEY_LENGTH} caracteres")
        if self.ai_provider == "gemini" and self.gemini_api_key is None:
            problems.append("GEMINI_API_KEY: falta (obligatoria con AI_PROVIDER=gemini)")
        return problems


def _is_postgres_url(url: str) -> bool:
    """Indica si la URL usa PostgreSQL, con o sin controlador (postgresql+psycopg://)."""
    scheme = url.split("://", 1)[0]
    return scheme.split("+", 1)[0] in _POSTGRES_SCHEMES


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración, leída una sola vez por proceso."""
    return Settings()
