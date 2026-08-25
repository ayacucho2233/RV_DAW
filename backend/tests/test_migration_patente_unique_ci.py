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
from sqlalchemy.orm import sessionmaker

from app.features.vehiculos import repository as vehiculos_repository
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


def test_obtener_por_patente_normalizada_usa_el_indice_lower(test_database_url: str):
    """FIX-004: `obtener_por_patente_normalizada` debe poder usar el índice
    único funcional que crea la migración 0003 (sobre `lower(patente)`).

    Antes del fix, la query comparaba con `func.upper(patente)` — una
    expresión distinta a `lower(patente)` para el planner de Postgres, que
    no puede usar un índice funcional sobre una expresión para resolver una
    condición sobre otra. El resultado seguía siendo correcto (ambos lados
    de la comparación usaban `upper()`), pero cada búsqueda por patente
    —incluida la de `crear_vehiculo`/`modificar_vehiculo`— hacía un
    `Seq Scan` en vez de un `Index Scan`, contradiciendo NFR-01 del PRD de
    FEAT-004 ("lookups indexados, O(log n)").

    Captura, vía el evento `before_cursor_execute`, el SQL exacto que
    SQLAlchemy manda a Postgres al llamar la función real (no una query
    reconstruida a mano en el test), y le antepone `EXPLAIN` para confirmar
    que el plan usa `ix_vehiculos_patente_lower_unique`.
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
                {"p": "ABC123"},
            )

        captured: dict = {}

        def _capturar(conn, cursor, statement, parameters, context, executemany):
            captured["statement"] = statement
            captured["parameters"] = parameters

        sa.event.listen(engine, "before_cursor_execute", _capturar)
        try:
            session_factory = sessionmaker(bind=engine)
            session = session_factory()
            try:
                vehiculo = vehiculos_repository.obtener_por_patente_normalizada(
                    session, "abc123"
                )
            finally:
                session.close()
        finally:
            sa.event.remove(engine, "before_cursor_execute", _capturar)

        assert vehiculo is not None
        assert "statement" in captured, "no se capturó ninguna query"

        raw_conn = engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            cursor.execute(f"EXPLAIN {captured['statement']}", captured["parameters"])
            plan_text = "\n".join(row[0] for row in cursor.fetchall())
        finally:
            raw_conn.close()

        assert "ix_vehiculos_patente_lower_unique" in plan_text, (
            "la query de obtener_por_patente_normalizada no usa el índice único "
            f"funcional. Plan real:\n{plan_text}"
        )
        assert "Seq Scan" not in plan_text, f"plan real:\n{plan_text}"
    finally:
        engine.dispose()

    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )


def test_obtener_por_patente_normalizada_usa_order_by_id(test_database_url: str):
    """FIX-005, regresión B1: la query de `obtener_por_patente_normalizada`
    incluye `ORDER BY vehiculos.id` — `.limit(1)` por sí solo no garantiza
    determinismo entre llamadas si hubiera más de una fila candidata.

    Se para en la revisión 0002 (sin el índice único todavía) a propósito:
    es el único estado donde pueden coexistir en la tabla dos filas cuyas
    patentes difieren solo en casing, que es el escenario que hace visible
    la falta de `ORDER BY`. Inspecciona el SQL COMPILADO capturado vía
    `before_cursor_execute` (no solo el resultado devuelto) — un resultado
    que "por casualidad" coincide no prueba determinismo real.
    """
    _run_alembic("downgrade", "base", database_url=test_database_url)
    result = _run_alembic("upgrade", "0002", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade 0002 falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"),
                {"p": "AbC123"},
            )
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'camioneta')"),
                {"p": "ABC123"},
            )

        captured: dict = {}

        def _capturar(conn, cursor, statement, parameters, context, executemany):
            captured["statement"] = statement

        sa.event.listen(engine, "before_cursor_execute", _capturar)
        try:
            session_factory = sessionmaker(bind=engine)
            session = session_factory()
            try:
                vehiculo = vehiculos_repository.obtener_por_patente_normalizada(
                    session, "abc123"
                )
            finally:
                session.close()
        finally:
            sa.event.remove(engine, "before_cursor_execute", _capturar)

        assert vehiculo is not None
        assert "statement" in captured, "no se capturó ninguna query"
        assert "ORDER BY vehiculos.id" in captured["statement"], (
            f"la query no ordena por id, no es determinística: {captured['statement']}"
        )
    finally:
        engine.dispose()

    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )


def test_migracion_0003_falla_con_mensaje_claro_si_hay_duplicados(test_database_url: str):
    """FIX-005, regresión C1: si ya existen en la tabla dos filas con la
    misma patente en distinto casing, `alembic upgrade head` (0002 -> 0003)
    falla con un `RuntimeError` de Python que menciona las patentes en
    conflicto — no con el error crudo de Postgres
    (`duplicate key value violates unique constraint`) sin contexto."""
    _run_alembic("downgrade", "base", database_url=test_database_url)
    result = _run_alembic("upgrade", "0002", database_url=test_database_url)
    assert result.returncode == 0, (
        f"alembic upgrade 0002 falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    engine = sa.create_engine(test_database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'auto')"),
                {"p": "DuP123"},
            )
            conn.execute(
                sa.text("INSERT INTO vehiculos (patente, tipo) VALUES (:p, 'camioneta')"),
                {"p": "DUP123"},
            )
    finally:
        engine.dispose()

    result_head = _run_alembic("upgrade", "head", database_url=test_database_url)
    assert result_head.returncode != 0, (
        "se esperaba que la migración 0003 fallara con duplicados existentes"
    )
    salida = (result_head.stdout + result_head.stderr).lower()
    assert "duplicate key value" not in salida, (
        "la migración dejó pasar el error crudo de Postgres en vez del RuntimeError "
        f"con contexto.\nstdout: {result_head.stdout}\nstderr: {result_head.stderr}"
    )
    assert "runtimeerror" in salida, (
        f"no se encontró el RuntimeError esperado.\nstdout: {result_head.stdout}\n"
        f"stderr: {result_head.stderr}"
    )
    assert "dup123" in salida, (
        f"el mensaje no menciona la patente en conflicto.\nstdout: {result_head.stdout}\n"
        f"stderr: {result_head.stderr}"
    )

    # Limpieza: vuelve a un estado limpio para no dejar la base a mitad de
    # una migración fallida entre corridas de test.
    downgrade_result = _run_alembic("downgrade", "base", database_url=test_database_url)
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base falló.\nstdout: {downgrade_result.stdout}\n"
        f"stderr: {downgrade_result.stderr}"
    )
