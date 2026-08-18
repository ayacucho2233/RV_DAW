"""patente unique case insensitive

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-17

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pre-chequeo de duplicados existentes (FIX-005, hallazgo C): sin esto,
    # `CREATE UNIQUE INDEX` falla con el error crudo de Postgres
    # (`duplicate key value violates unique constraint`), sin decir qué
    # patentes están en conflicto. Ventana TOCTOU aceptada entre este
    # `SELECT` y el `CREATE UNIQUE INDEX` de abajo (riesgo aceptado F-TM-04
    # del threat model de FIX-005): las migraciones de este proyecto corren
    # en una ventana de mantenimiento sin escritura concurrente, mismo
    # supuesto que ya hacía el chequeo manual documentado en el PRD de
    # FEAT-004 que este código reemplaza.
    bind = op.get_bind()
    duplicados = bind.execute(
        sa.text(
            "SELECT lower(patente) AS patente_normalizada, COUNT(*) AS cantidad "
            "FROM vehiculos GROUP BY lower(patente) HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if duplicados:
        conflictos = ", ".join(
            f"{fila.patente_normalizada!r} ({fila.cantidad} filas)" for fila in duplicados
        )
        raise RuntimeError(
            "No se puede crear el índice único ix_vehiculos_patente_lower_unique: "
            f"hay patentes duplicadas (case-insensitive) en la tabla vehiculos: {conflictos}. "
            "Resolvé los duplicados antes de reintentar la migración."
        )

    op.create_index(
        "ix_vehiculos_patente_lower_unique",
        "vehiculos",
        [sa.text("lower(patente)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_vehiculos_patente_lower_unique", table_name="vehiculos")
