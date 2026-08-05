"""create reservas table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "vehiculo_id",
            sa.Integer(),
            sa.ForeignKey("vehiculos.id"),
            nullable=False,
        ),
        sa.Column("nombre_empleado", sa.String(length=200), nullable=False),
        sa.Column("legajo", sa.String(length=20), nullable=False),
        sa.Column("licencia", sa.String(length=20), nullable=False),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("destino", sa.String(length=200), nullable=False),
        sa.Column(
            "estado",
            sa.Enum(
                "activa",
                "cancelada",
                name="estado_reserva",
                native_enum=False,
                length=10,
                create_constraint=True,
            ),
            nullable=False,
            server_default="activa",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "fecha_fin > fecha_inicio", name="ck_reservas_fecha_fin_mayor_inicio"
        ),
    )
    op.create_index(
        "ix_reservas_vehiculo_fechas",
        "reservas",
        ["vehiculo_id", "fecha_inicio", "fecha_fin"],
    )


def downgrade() -> None:
    op.drop_index("ix_reservas_vehiculo_fechas", table_name="reservas")
    op.drop_table("reservas")
