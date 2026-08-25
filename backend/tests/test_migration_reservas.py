"""Test de la migración `0002_create_reservas` (Block 1 de FEAT-001c).

Corre `alembic upgrade head` contra una base de datos de test real, partiendo
de la migración `0001` de FEAT-001a, y verifica que la tabla `reservas` queda
creada con las columnas y constraints declaradas en el spec: el CHECK
`fecha_fin > fecha_inicio`, la FK a `vehiculos.id` y el índice compuesto
`(vehiculo_id, fecha_inicio, fecha_fin)`.
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


def test_migracion_crea_tabla_reservas(test_database_url: str):
    # Empieza desde un estado limpio por si una corrida previa dejó las tablas.
    _run_alembic("downgrade", "base", database_url=test_database_url)

    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        inspector = sa.inspect(engine)
        assert "reservas" in inspector.get_table_names()

        columns = {col["name"]: col for col in inspector.get_columns("reservas")}
        assert set(columns) == {
            "id",
            "vehiculo_id",
            "nombre_empleado",
            "legajo",
            "licencia",
            "fecha_inicio",
            "fecha_fin",
            "destino",
            "estado",
            "created_at",
            "updated_at",
        }

        for col_name in columns:
            assert columns[col_name]["nullable"] is False, (
                f"la columna '{col_name}' debería ser NOT NULL"
            )

        # DEFAULT de estado == 'activa'
        assert columns["estado"]["default"] is not None
        assert "activa" in columns["estado"]["default"]

        pk = inspector.get_pk_constraint("reservas")
        assert pk["constrained_columns"] == ["id"]

        # FK a vehiculos.id, declarada y activa a nivel de DB.
        fks = inspector.get_foreign_keys("reservas")
        vehiculo_fks = [fk for fk in fks if fk["constrained_columns"] == ["vehiculo_id"]]
        assert vehiculo_fks, "no hay FK sobre vehiculo_id"
        assert vehiculo_fks[0]["referred_table"] == "vehiculos"
        assert vehiculo_fks[0]["referred_columns"] == ["id"]

        # Índice compuesto explícito (vehiculo_id, fecha_inicio, fecha_fin).
        indexes = inspector.get_indexes("reservas")
        compuesto = [
            idx
            for idx in indexes
            if idx["column_names"] == ["vehiculo_id", "fecha_inicio", "fecha_fin"]
        ]
        assert compuesto, (
            f"no se encontró el índice compuesto (vehiculo_id, fecha_inicio, fecha_fin); "
            f"índices existentes: {indexes}"
        )

        # CHECK de fecha_fin > fecha_inicio y de estado, a nivel de DB.
        check_constraints = inspector.get_check_constraints("reservas")
        check_texts = " ".join(c["sqltext"] for c in check_constraints)
        assert "fecha_fin" in check_texts and "fecha_inicio" in check_texts, (
            f"no se encontró un CHECK de fecha_fin > fecha_inicio; constraints: {check_constraints}"
        )
        assert "estado" in check_texts, (
            f"no se encontró un CHECK sobre 'estado'; constraints: {check_constraints}"
        )

        # Comportamiento: crear un vehículo válido primero.
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"),
                {"p": "AA111BB"},
            )
            vehiculo_id = conn.execute(
                sa.text("SELECT id FROM vehiculos WHERE patente = :p"), {"p": "AA111BB"}
            ).scalar()

        # El CHECK de fecha_fin > fecha_inicio rechaza un rango invertido.
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO reservas "
                    "(vehiculo_id, nombre_empleado, legajo, licencia, "
                    "fecha_inicio, fecha_fin, destino) "
                    "VALUES (:vid, 'Juan Perez', '123', 'B1', "
                    "'2026-08-10T10:00:00+00:00', '2026-08-09T10:00:00+00:00', 'Rosario')"
                ),
                {"vid": vehiculo_id},
            )

        # El CHECK de estado rechaza un valor fuera del enum.
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO reservas "
                    "(vehiculo_id, nombre_empleado, legajo, licencia, "
                    "fecha_inicio, fecha_fin, destino, estado) "
                    "VALUES (:vid, 'Juan Perez', '123', 'B1', "
                    "'2026-08-09T10:00:00+00:00', '2026-08-10T10:00:00+00:00', "
                    "'Rosario', 'pendiente')"
                ),
                {"vid": vehiculo_id},
            )

        # Un INSERT válido debe funcionar (evidencia de que las constraints
        # anteriores no son falsos positivos que bloqueen el caso normal).
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO reservas "
                    "(vehiculo_id, nombre_empleado, legajo, licencia, "
                    "fecha_inicio, fecha_fin, destino) "
                    "VALUES (:vid, 'Juan Perez', '123', 'B1', "
                    "'2026-08-09T10:00:00+00:00', '2026-08-10T10:00:00+00:00', 'Rosario')"
                ),
                {"vid": vehiculo_id},
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
        assert "reservas" not in inspector.get_table_names()
        assert "vehiculos" not in inspector.get_table_names()
    finally:
        engine.dispose()


def test_migracion_reservas_requiere_vehiculo_existente(test_database_url: str):
    _run_alembic("downgrade", "base", database_url=test_database_url)
    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO reservas "
                    "(vehiculo_id, nombre_empleado, legajo, licencia, "
                    "fecha_inicio, fecha_fin, destino) "
                    "VALUES (:vid, 'Juan Perez', '123', 'B1', "
                    "'2026-08-09T10:00:00+00:00', '2026-08-10T10:00:00+00:00', 'Rosario')"
                ),
                {"vid": 999999},
            )
    finally:
        engine.dispose()

    _run_alembic("downgrade", "base", database_url=test_database_url)


def test_migracion_agrega_caducada_al_check(test_database_url: str):
    """Test de la migración `0004_estado_caducada` (Block 1 de FEAT-005).

    Tras `upgrade head`, el CHECK `estado_reserva` debe aceptar `'caducada'`
    como tercer valor válido, y seguir rechazando cualquier valor fuera del
    enum.
    """
    _run_alembic("downgrade", "base", database_url=test_database_url)
    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"),
                {"p": "AA111CC"},
            )
            vehiculo_id = conn.execute(
                sa.text("SELECT id FROM vehiculos WHERE patente = :p"), {"p": "AA111CC"}
            ).scalar()
            conn.execute(
                sa.text(
                    "INSERT INTO reservas "
                    "(vehiculo_id, nombre_empleado, legajo, licencia, "
                    "fecha_inicio, fecha_fin, destino) "
                    "VALUES (:vid, 'Juan Perez', '123', 'B1', "
                    "'2026-08-09T10:00:00+00:00', '2026-08-10T10:00:00+00:00', 'Rosario')"
                ),
                {"vid": vehiculo_id},
            )
            reserva_id = conn.execute(
                sa.text("SELECT id FROM reservas WHERE vehiculo_id = :vid"),
                {"vid": vehiculo_id},
            ).scalar()

        # 'caducada' es un valor válido tras la migración: no viola el CHECK.
        with engine.begin() as conn:
            conn.execute(
                sa.text("UPDATE reservas SET estado = 'caducada' WHERE id = :rid"),
                {"rid": reserva_id},
            )

        # Un valor fuera del enum sigue violando el CHECK ('pendiente' entra
        # en el largo de columna VARCHAR(10), a diferencia de 'inexistente',
        # para que la violación sea del CHECK y no del límite de longitud).
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                sa.text("UPDATE reservas SET estado = 'pendiente' WHERE id = :rid"),
                {"rid": reserva_id},
            )
        # Limpieza previa al downgrade: una fila en 'caducada' haría fallar
        # el propio downgrade (ver comentario en 0004_estado_caducada.py),
        # y dejaría la base sucia para el resto de la suite.
        with engine.begin() as conn:
            conn.execute(
                sa.text("DELETE FROM reservas WHERE id = :rid"), {"rid": reserva_id}
            )
    finally:
        engine.dispose()

    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )


def test_migracion_no_reescribe_filas_existentes(test_database_url: str):
    """AC-06: la migración `0004` amplía solo el CHECK y agrega un índice —
    no debe tocar (ni mediante DML ni por efecto de un `ALTER` que reescriba
    filas) reservas `activa` ya vencidas que existían antes de aplicarla.
    """
    _run_alembic("downgrade", "base", database_url=test_database_url)
    # Aplica hasta 0003 (antes de la migración bajo test) e inserta la fila.
    result = _run_alembic("upgrade", "0003", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade 0003 falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"),
                {"p": "AA111DD"},
            )
            vehiculo_id = conn.execute(
                sa.text("SELECT id FROM vehiculos WHERE patente = :p"), {"p": "AA111DD"}
            ).scalar()
            conn.execute(
                sa.text(
                    "INSERT INTO reservas "
                    "(vehiculo_id, nombre_empleado, legajo, licencia, "
                    "fecha_inicio, fecha_fin, destino) "
                    "VALUES (:vid, 'Juan Perez', '123', 'B1', "
                    "'2020-01-01T10:00:00+00:00', '2020-01-02T10:00:00+00:00', 'Rosario')"
                ),
                {"vid": vehiculo_id},
            )
            reserva_id = conn.execute(
                sa.text("SELECT id FROM reservas WHERE vehiculo_id = :vid"),
                {"vid": vehiculo_id},
            ).scalar()
    finally:
        engine.dispose()

    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        with engine.begin() as conn:
            # Confirma que la migración 0004 realmente se aplicó (no solo
            # que "upgrade head" fue un no-op porque el archivo no existe).
            version = conn.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar()
            assert version == "0004", (
                f"la cadena no llegó a la migración 0004; version_num={version!r}"
            )

            row = conn.execute(
                sa.text(
                    "SELECT estado, fecha_fin FROM reservas WHERE id = :rid"
                ),
                {"rid": reserva_id},
            ).one()
        assert row.estado == "activa", (
            "la migración 0004 no debe reescribir reservas activas preexistentes"
        )
    finally:
        engine.dispose()

    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )


def test_migracion_crea_indice_estado_fecha_fin(test_database_url: str):
    """Mitigación M-01 del threat model: la migración `0004` debe crear el
    índice compuesto `(estado, fecha_fin)` para que el UPDATE masivo de
    `caducar_vencidas` (Block 2) no haga full scan.
    """
    _run_alembic("downgrade", "base", database_url=test_database_url)
    result = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade head falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        inspector = sa.inspect(engine)
        indexes = inspector.get_indexes("reservas")
        estado_fecha_fin = [
            idx
            for idx in indexes
            if idx["name"] == "ix_reservas_estado_fecha_fin"
        ]
        assert estado_fecha_fin, (
            f"no se encontró el índice 'ix_reservas_estado_fecha_fin'; índices existentes: {indexes}"
        )
        assert estado_fecha_fin[0]["column_names"] == ["estado", "fecha_fin"]
    finally:
        engine.dispose()

    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )
