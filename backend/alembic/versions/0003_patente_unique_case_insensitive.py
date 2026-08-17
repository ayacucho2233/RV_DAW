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
    op.create_index(
        "ix_vehiculos_patente_lower_unique",
        "vehiculos",
        [sa.text("lower(patente)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_vehiculos_patente_lower_unique", table_name="vehiculos")
