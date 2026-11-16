"""Crear la tabla de productos del catálogo (PED-88).

Revision ID: cc5556642e8d
Revises:
Create Date: 2026-11-16 10:23:58.969870
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "cc5556642e8d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Aplica la migración."""
    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("name_key", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("tracks_inventory", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("price > 0 AND price <= 100000000", name="ck_product_price_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Índice único parcial: dos productos activos no pueden compartir nombre normalizado.
    op.create_index(
        "ux_product_active_name",
        "product",
        ["name_key"],
        unique=True,
        sqlite_where=sa.text("is_active"),
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    """Revierte la migración."""
    op.drop_index("ux_product_active_name", table_name="product")
    op.drop_table("product")
