"""Test de la migración inicial `0001_create_vehiculos`.

Corre `alembic upgrade head` contra una base de datos de test real y
verifica que la tabla `vehiculos` queda creada con las columnas y
constraints declaradas en el spec (incluye el UNIQUE de `patente`).
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


def test_migracion_crea_tabla_vehiculos(test_database_url: str):
    # Empieza desde un estado limpio por si una corrida previa dejó la tabla.
    _run_alembic("downgrade", "base", database_url=test_database_url)

    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        inspector = sa.inspect(engine)
        assert "vehiculos" in inspector.get_table_names()

        columns = {col["name"]: col for col in inspector.get_columns("vehiculos")}
        assert set(columns) == {
            "id",
            "patente",
            "tipo",
            "estado",
            "created_at",
            "updated_at",
        }

        assert columns["id"]["nullable"] is False
        assert columns["patente"]["nullable"] is False
        assert columns["tipo"]["nullable"] is False
        assert columns["estado"]["nullable"] is False
        assert columns["created_at"]["nullable"] is False
        assert columns["updated_at"]["nullable"] is False

        # DEFAULT de estado == 'activo'
        assert columns["estado"]["default"] is not None
        assert "activo" in columns["estado"]["default"]

        pk = inspector.get_pk_constraint("vehiculos")
        assert pk["constrained_columns"] == ["id"]

        # Índice (único) explícito en patente — en Postgres, `unique=True` +
        # `index=True` sobre la columna se traduce en un único índice único
        # (no aparece por separado en `get_unique_constraints`, que solo
        # lista constraints agregadas con ALTER TABLE ... ADD CONSTRAINT).
        indexes = inspector.get_indexes("vehiculos")
        patente_indexes = [idx for idx in indexes if idx["column_names"] == ["patente"]]
        assert patente_indexes, "no hay índice sobre patente"
        assert patente_indexes[0]["unique"] is True

        # Verificación de comportamiento (la que realmente importa para
        # FR-08): la restricción UNIQUE debe rechazar patentes duplicadas.
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"
                ),
                {"p": "AA123BB"},
            )
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'camioneta')"
                ),
                {"p": "AA123BB"},
            )

        # CHECK de `tipo`/`estado` a nivel de DB (defensa en profundidad:
        # models.py declara `create_constraint=True` en el Enum, la
        # migración debe emitir el mismo CHECK, no solo confiar en que
        # Pydantic valide en Block 2). Verificamos tanto que la constraint
        # exista en el catálogo como que la DB rechace un valor inválido
        # insertado directamente (bypaseando cualquier validación de app).
        check_constraints = inspector.get_check_constraints("vehiculos")
        check_texts = " ".join(c["sqltext"] for c in check_constraints)
        assert "tipo" in check_texts, (
            f"no se encontró un CHECK sobre 'tipo' en la tabla; constraints: {check_constraints}"
        )
        assert "estado" in check_texts, (
            f"no se encontró un CHECK sobre 'estado' en la tabla; constraints: {check_constraints}"
        )

        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'moto')"
                ),
                {"p": "ZZ999ZZ"},
            )
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO vehiculos (patente, tipo, estado) "
                    "VALUES (:p, 'auto', 'inexistente')"
                ),
                {"p": "ZZ999ZZ"},
            )
    finally:
        engine.dispose()

    # El rollback también debe correr limpio (criterio de completitud del bloque).
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
