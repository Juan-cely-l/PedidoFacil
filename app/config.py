"""Configuración de la aplicación leída desde variables de entorno (o un archivo .env local)."""

import os
import secrets
from functools import lru_cache
from typing import Annotated, Literal, Self, cast

from fastapi import Request
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.services.auth import normalize_email

# Fuera de producción no hace falta definir DATABASE_URL: se usa SQLite.
_DEFAULT_DATABASE_URLS = {"test": "sqlite://", "local": "sqlite:///./pedidofacil.db"}
# Fuera de producción, la URL desde la que se abre la app (la URI de vuelta de Google sale de aquí).
_DEFAULT_PUBLIC_BASE_URLS = {"test": "http://testserver", "local": "http://127.0.0.1:8000"}
_OAUTH_CALLBACK_PATH = "/auth/google/callback"
_POSTGRES_SCHEMES = ("postgresql", "postgres")
_MIN_SECRET_KEY_LENGTH = 32
_LOCAL_HINT = "Para desarrollo local copia .env.example a .env (ENVIRONMENT=local)"
# Valor de GEMINI_FALLBACK_MODEL que desactiva el respaldo (vacía cuenta como ausente).
_NO_FALLBACK = "ninguno"
# Principio V: respaldo manual si la IA tarda más de 15 s; nunca se configura un tope mayor.
_MAX_AI_TIMEOUT_SECONDS = 15


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
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] | None = None
    # Render define RENDER_GIT_COMMIT en cada despliegue: permite saber qué commit está corriendo.
    git_commit: str = Field(default="local", validation_alias="RENDER_GIT_COMMIT")
    database_url: SecretStr | None = None
    secret_key: SecretStr | None = None
    ai_provider: Literal["fake", "gemini"] | None = None
    gemini_api_key: SecretStr | None = None
    # Cotización con IA (PED-16): los modelos se cambian según la medición (research.md R2).
    gemini_model: str = "gemini-3.5-flash-lite"
    # Sin respaldo por defecto: la medición descartó gemini-3.8-flash y gemini-3.5-flash no cabe
    # en el tiempo de espera (research.md R2). Un entorno nuevo no debe usar en silencio un
    # modelo descartado.
    gemini_fallback_model: str | None = None
    ai_timeout_seconds: float = Field(default=10, gt=0, le=_MAX_AI_TIMEOUT_SECONDS)
    # Login del dueño con Google OAuth 2.0 / OpenID Connect (ADR 0003).
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    # Lista blanca: correos separados por comas en la variable; aquí, ya normalizados.
    owner_emails: Annotated[frozenset[str], NoDecode] = frozenset()
    # URL pública de la app; la URI de vuelta de Google sale de aquí.
    public_base_url: str | None = None
    # Render publica la URL del servicio: se usa si PUBLIC_BASE_URL no está definida.
    render_external_url: str | None = Field(default=None, validation_alias="RENDER_EXTERNAL_URL")

    @field_validator("owner_emails", mode="before")
    @classmethod
    def _parse_owner_emails(cls, value: object) -> object:
        """Separa por comas, normaliza cada correo y descarta los vacíos."""
        if isinstance(value, str):
            emails = (normalize_email(email) for email in value.split(","))
            return frozenset(email for email in emails if email)
        return value

    @field_validator("gemini_model")
    @classmethod
    def _require_model_name(cls, value: str) -> str:
        """El modelo principal no puede quedar en blanco."""
        name = value.strip()
        if not name:
            raise ValueError("GEMINI_MODEL: no puede quedar en blanco")
        return name

    @field_validator("gemini_fallback_model")
    @classmethod
    def _parse_fallback_model(cls, value: str | None) -> str | None:
        """«ninguno» desactiva el respaldo; en blanco no es un nombre de modelo."""
        if value is None:
            return None
        name = value.strip()
        if name.lower() == _NO_FALLBACK:
            return None
        if not name:
            raise ValueError(
                f"GEMINI_FALLBACK_MODEL: no puede quedar en blanco ({_NO_FALLBACK!r} lo desactiva)"
            )
        return name

    @model_validator(mode="after")
    def _apply_environment_rules(self) -> Self:
        """Completa los valores por ambiente y, en producción, exige las variables obligatorias."""
        if self.gemini_fallback_model == self.gemini_model:
            raise ValueError(
                "GEMINI_FALLBACK_MODEL: debe ser distinto de GEMINI_MODEL "
                f"(usa {_NO_FALLBACK!r} para desactivar el respaldo)"
            )
        if self.log_level is None:
            self.log_level = "DEBUG" if self.environment == "local" else "INFO"
        if self.public_base_url is None:
            self.public_base_url = self.render_external_url
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
        if self.public_base_url is None:
            self.public_base_url = _DEFAULT_PUBLIC_BASE_URLS[self.environment]
        return self

    @property
    def docs_enabled(self) -> bool:
        """La documentación interactiva de la API solo se publica fuera de producción."""
        return self.environment != "production"

    @property
    def oauth_redirect_uri(self) -> str:
        """URI a la que Google devuelve al dueño; debe estar registrada en Google Cloud."""
        # Settings garantiza la URL tras validarse: obligatoria en producción, por defecto fuera.
        base_url = cast(str, self.public_base_url).rstrip("/")
        return f"{base_url}{_OAUTH_CALLBACK_PATH}"

    @property
    def short_commit(self) -> str:
        """Commit desplegado en 7 caracteres (o "local" si la plataforma no lo informa)."""
        return self.git_commit[:7]

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
        if self.google_client_id is None:
            problems.append("GOOGLE_CLIENT_ID: falta (ID del cliente OAuth de Google)")
        if self.google_client_secret is None:
            problems.append("GOOGLE_CLIENT_SECRET: falta (secreto del cliente OAuth de Google)")
        if not self.owner_emails:
            problems.append("OWNER_EMAILS: falta (al menos un correo autorizado a entrar)")
        if self.public_base_url is None:
            problems.append("PUBLIC_BASE_URL: falta (URL pública de la app, con https://)")
        elif not self.public_base_url.startswith("https://"):
            problems.append("PUBLIC_BASE_URL: debe empezar por https://")
        return problems


def _is_postgres_url(url: str) -> bool:
    """Indica si la URL usa PostgreSQL, con o sin controlador (postgresql+psycopg://)."""
    scheme = url.split("://", 1)[0]
    return scheme.split("+", 1)[0] in _POSTGRES_SCHEMES


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración, leída una sola vez por proceso.

    El ambiente se toma del proceso (no del .env), porque decide si el .env se lee: en test
    nunca, para que los valores locales del desarrollador no alteren las pruebas.
    """
    if os.environ.get("ENVIRONMENT") == "test":
        return Settings(_env_file=None)
    return Settings()


def get_app_settings(request: Request) -> Settings:
    """Dependencia de FastAPI: la configuración con la que se creó la app (app.state)."""
    settings: Settings = request.app.state.settings
    return settings
