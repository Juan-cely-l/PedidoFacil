"""Crear la tabla de variantes de producto (PED-88).

Revision ID: e9fd0f23227f
Revises: cc5556642e8d
Create Date: 2026-11-17 05:44:09.757796
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "e9fd0f23227f"
down_revision: str | Sequence[str] | None = "cc5556642e8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Aplica la migración."""
    op.create_table(
        "product_variant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
        sa.Column("value", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("value_key", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('sabor', 'peso', 'color', 'marca', 'tamano')", name="ck_variant_kind"
        ),
        sa.CheckConstraint(
            "price IS NULL OR (price > 0 AND price <= 100000000)", name="ck_variant_price_range"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_product_variant_product_id", "product_variant", ["product_id"], unique=False
    )
    # Índice único parcial: un producto no puede tener dos variantes activas iguales.
    op.create_index(
        "ux_variant_active_kind_value",
        "product_variant",
        ["product_id", "kind", "value_key"],
        unique=True,
        sqlite_where=sa.text("is_active"),
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    """Revierte la migración."""
    op.drop_index("ux_variant_active_kind_value", table_name="product_variant")
    op.drop_index("ix_product_variant_product_id", table_name="product_variant")
    op.drop_table("product_variant")
