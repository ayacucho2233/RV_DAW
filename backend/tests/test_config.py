"""Tests de `app.core.config`.

Cubren el Block 1 del spec FEAT-001a: la config debe exponer las 4
variables requeridas cuando están presentes, y fallar de forma explícita
al importar/instanciar si falta `DATABASE_URL` (nunca arrancar con un
default silencioso).
"""
import importlib
import sys

import pytest
from pydantic import ValidationError

from tests.conftest import REQUIRED_ENV


def _reload_config():
    """Recarga app.core.config para que relea las env vars actuales."""
    sys.modules.pop("app.core.config", None)
    return importlib.import_module("app.core.config")


def _reload_config_sin_env_file():
    """Recarga app.core.config ignorando backend/.env.

    A diferencia de `_reload_config`, instancia `Settings` con `_env_file=None`
    para que la lectura dependa exclusivamente de `os.environ`: `Settings` usa
    `SettingsConfigDict(env_file=".env")`, así que un `monkeypatch.delenv` por
    sí solo no simula la ausencia real de la variable si `.env` sigue
    proveyéndola en el filesystem.
    """
    config = _reload_config()
    return config.Settings(_env_file=None)


def test_config_carga_variables_requeridas(monkeypatch: pytest.MonkeyPatch):
    config = _reload_config()

    assert config.settings.DATABASE_URL == REQUIRED_ENV["DATABASE_URL"]
    assert config.settings.ADMIN_USERNAME == REQUIRED_ENV["ADMIN_USERNAME"]
    assert config.settings.ADMIN_PASSWORD_HASH == REQUIRED_ENV["ADMIN_PASSWORD_HASH"]
    assert config.settings.FRONTEND_ORIGIN == REQUIRED_ENV["FRONTEND_ORIGIN"]


def test_config_falla_sin_database_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Debe fallar específicamente por validación (falta un campo requerido de
    # Settings), no por cualquier otro motivo — así el test no puede pasar
    # "por accidente" antes de que exista la implementación.
    with pytest.raises(ValidationError) as exc_info:
        _reload_config_sin_env_file()

    assert "DATABASE_URL" in str(exc_info.value)
