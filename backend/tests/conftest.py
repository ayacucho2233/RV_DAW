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

# Setea las variables ya al cargar este módulo (no solo en la fixture de
# abajo): `app.core.database`/`app.core.config` se importan a nivel de
# módulo desde los tests de Block 2 (`service.py`, `repository.py`), y esos
# imports pueden ocurrir durante la fase de *collection* de pytest, antes de
# que corra ninguna fixture. Sin esto, `Settings()` fallaría al importar por
# falta de env vars en ese momento. `setdefault` no pisa nada si el entorno
# ya trae sus propios valores (p. ej. en CI).
for _key, _value in REQUIRED_ENV.items():
    os.environ.setdefault(_key, _value)


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


@pytest.fixture
def db_session(test_database_url: str):
    """Sesión de SQLAlchemy contra la base de datos de test real (Block 2+).

    Crea todas las tablas registradas en `Base.metadata` (incluye
    `vehiculos`, de Block 1) antes del test y las dropea al terminar, para
    que cada test arranque desde un estado limpio sin depender de invocar
    `alembic` (eso ya lo cubre `test_migracion_crea_tabla_vehiculos` de
    Block 1). Compartida entre bloques: Block 3 la reutilizará para sus
    tests de endpoint.
    """
    import app.features.reservas.models  # noqa: F401 — registra el modelo en Base.metadata
    import app.features.vehiculos.models  # noqa: F401 — registra el modelo en Base.metadata
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base

    engine = create_engine(test_database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
