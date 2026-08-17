"""Test de la migración `0003_patente_unique_case_insensitive` (Block 1 de
spec-FEAT-004).

Corre `alembic upgrade head` contra una base de datos de test real y
verifica que el índice único funcional sobre `lower(patente)` queda
efectivamente creado y aplicado por Postgres — no solo que el pre-chequeo de
`service.py` funciona (eso ya lo cubren los tests de
`test_vehiculos_service.py`, que usan la fixture `db_session`, la cual crea
las tablas vía `Base.metadata.create_all()` y por lo tanto NO pasa por esta
migración). Este test bypasea `service.py` por completo: hace dos `INSERT`
directos con patentes que solo difieren en casing y confirma que el segundo
es rechazado por la base.
"""
import os
import pathlib
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.conftest import REQUIRED_ENV

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(REQUIRED_ENV)
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_indice_unico_case_insensitive_a_nivel_db(test_database_url: str):
    # Empieza desde un estado limpio por si una corrida previa dejó las tablas.
    _run_alembic("downgrade", "base", database_url=test_database_url)

    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        inspector = sa.inspect(engine)
        indexes = inspector.get_indexes("vehiculos")
        assert any(
            idx["name"] == "ix_vehiculos_patente_lower_unique" for idx in indexes
        ), f"no se encontró el índice único funcional; índices existentes: {indexes}"

        # Comportamiento: dos INSERTs directos (bypaseando service.py) con
        # patentes que solo difieren en casing — el segundo debe fallar con
        # IntegrityError, confirmando que el índice está realmente aplicado.
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"
                ),
                {"p": "AbC123"},
            )
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'camioneta')"
                ),
                {"p": "ABC123"},
            )

        # El UNIQUE exacto ya existente (0001) sigue intacto y no fue tocado.
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"
                ),
                {"p": "AbC123"},
            )
    finally:
        engine.dispose()

    # El rollback también debe correr limpio.
    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )
    engine = sa.create_engine(test_database_url)
    try:
        inspector = sa.inspect(engine)
        assert "vehiculos" not in inspector.get_table_names()
    finally:
        engine.dispose()
