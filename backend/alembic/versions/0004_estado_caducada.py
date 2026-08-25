"""estado caducada

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-18

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # El nombre real del constraint, confirmado contra la base
    # (`\d reservas` -> `"estado_reserva" CHECK (...)`), es literalmente
    # `estado_reserva`, no `ck_reservas_estado_reserva`.
    op.drop_constraint("estado_reserva", "reservas", type_="check")
    op.create_check_constraint(
        "estado_reserva", "reservas", "estado IN ('activa', 'cancelada', 'caducada')"
    )
    # Mitigación M-01 del threat model (threat-FEAT-005.md): sin este
    # índice, el UPDATE masivo de `caducar_vencidas` (WHERE estado='activa'
    # AND fecha_fin < ahora) hace full scan en cada llamada.
    op.create_index(
        "ix_reservas_estado_fecha_fin", "reservas", ["estado", "fecha_fin"]
    )


def downgrade() -> None:
    # Nota: este downgrade falla si ya existen filas en 'caducada' al
    # momento de correrlo (el CHECK de 2 valores las rechazaría). Aceptable
    # porque los tests de migración (test_migration.py,
    # test_migration_reservas.py, test_migration_patente_unique_ci.py)
    # corren la cadena completa contra una base vacía.
    op.drop_index("ix_reservas_estado_fecha_fin", table_name="reservas")
    op.drop_constraint("estado_reserva", "reservas", type_="check")
    op.create_check_constraint(
        "estado_reserva", "reservas", "estado IN ('activa', 'cancelada')"
    )
