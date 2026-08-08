"""Carga de configuración desde variables de entorno.

Sin valores por defecto para secretos: si falta alguna variable requerida,
`Settings()` falla al instanciarse (pydantic `ValidationError`), lo que
aborta el arranque de la app en vez de arrancar con un default silencioso
(ver AGENTS.md — "Usar variables de entorno para credenciales... nunca
hardcodear").
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno requeridas por el backend.

    Ninguno de estos campos tiene un default: si falta alguno en el
    entorno (ni en `.env`), pydantic-settings levanta `ValidationError` al
    instanciar `Settings()`.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD_HASH: str
    FRONTEND_ORIGIN: str


settings = Settings()
