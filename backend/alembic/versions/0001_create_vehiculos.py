"""create vehiculos table

Revision ID: 0001
Revises:
Create Date: 2026-08-02

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehiculos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patente", sa.String(length=10), nullable=False, unique=True, index=True),
        sa.Column(
            "tipo",
            sa.Enum(
                "auto",
                "camioneta",
                name="tipo_vehiculo",
                native_enum=False,
                length=10,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.Enum(
                "activo",
                "baja_temporal",
                "baja_definitiva",
                name="estado_vehiculo",
                native_enum=False,
                length=20,
                create_constraint=True,
            ),
            nullable=False,
            server_default="activo",
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
    )


def downgrade() -> None:
    op.drop_table("vehiculos")
