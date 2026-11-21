"""Crear las tablas de cotizaciones y sus líneas (PED-16).

Revision ID: 614686bd97d9
Revises: e9fd0f23227f
Create Date: 2026-11-21 11:01:54.315546
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "614686bd97d9"
down_revision: str | Sequence[str] | None = "e9fd0f23227f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Aplica la migración."""
    op.create_table(
        "quote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
        sa.Column(
            "customer_message", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ai_outcome", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("ai_duration_ms", sa.Integer(), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("delivery_date_needs_review", sa.Boolean(), nullable=False),
        sa.Column("delivery_time", sa.Time(), nullable=True),
        sa.Column("delivery_time_needs_review", sa.Boolean(), nullable=False),
        sa.Column("delivery_mode", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=True),
        sa.Column("delivery_mode_needs_review", sa.Boolean(), nullable=False),
        sa.Column("delivery_address", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.CheckConstraint(
            "ai_outcome IN ('ok', 'timeout', 'provider_error', 'invalid_output', 'disabled')",
            name="ck_quote_ai_outcome",
        ),
        sa.CheckConstraint(
            "delivery_mode IS NULL OR delivery_mode IN ('domicilio', 'recoger')",
            name="ck_quote_delivery_mode",
        ),
        sa.CheckConstraint("status IN ('borrador')", name="ck_quote_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    # La lista de cotizaciones se ordena por fecha de creación.
    op.create_index("ix_quote_created_at", "quote", ["created_at"], unique=False)

    op.create_table(
        "quote_line",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("customer_text", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
        sa.Column("review_reason", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
        sa.Column("unit_price", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("quantity_assumed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "(status = 'lista' AND product_id IS NOT NULL AND unit_price IS NOT NULL "
            "AND quantity IS NOT NULL AND label IS NOT NULL AND review_reason IS NULL) "
            "OR (status = 'por_revisar' AND unit_price IS NULL AND review_reason IS NOT NULL)",
            name="ck_quote_line_invariant",
        ),
        sa.CheckConstraint(
            "review_reason IS NULL OR review_reason IN "
            "('no_reconocido', 'falta_variante', 'cantidad_invalida')",
            name="ck_quote_line_review_reason",
        ),
        sa.CheckConstraint("status IN ('lista', 'por_revisar')", name="ck_quote_line_status"),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity BETWEEN 1 AND 999", name="ck_quote_line_quantity"
        ),
        sa.CheckConstraint("unit_price IS NULL OR unit_price > 0", name="ck_quote_line_unit_price"),
        sa.CheckConstraint(
            "variant_id IS NULL OR product_id IS NOT NULL", name="ck_quote_line_variant_product"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["quote_id"], ["quote.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variant.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_line_quote_id", "quote_line", ["quote_id"], unique=False)


def downgrade() -> None:
    """Revierte la migración."""
    op.drop_index("ix_quote_line_quote_id", table_name="quote_line")
    op.drop_table("quote_line")
    op.drop_index("ix_quote_created_at", table_name="quote")
    op.drop_table("quote")
