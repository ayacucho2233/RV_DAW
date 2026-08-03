"""Fixtures compartidas para los tests del backend.

Provee, por defecto, las variables de entorno que `app.core.config` requiere
para poder importarse (ver AGENTS.md: nunca defaults silenciosos para
secretos). Los tests que necesitan simular una variable ausente la borran
explícitamente con `monkeypatch.delenv`.
"""
import os

import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://testuser@127.0.0.1:5433/reserva_vehiculos_test",
)

REQUIRED_ENV = {
    "DATABASE_URL": TEST_DATABASE_URL,
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD_HASH": "$2b$12$KIXQb4y5z6z6z6z6z6z6zuHqz6z6z6z6z6z6z6z6z6z6z6z6z6z6z",
    "FRONTEND_ORIGIN": "http://localhost:5173",
}


@pytest.fixture
def test_database_url() -> str:
    return TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def _required_env(monkeypatch: pytest.MonkeyPatch):
    """Setea las 4 variables requeridas antes de cada test.

    Los tests que necesitan probar la ausencia de una variable la borran
    ellos mismos, después de que esta fixture las setea (el orden de
    ejecución dentro del test corre después del setup de fixtures).
    """
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
