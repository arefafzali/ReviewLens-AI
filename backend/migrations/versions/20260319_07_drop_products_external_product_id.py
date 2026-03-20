"""Drop unused products.external_product_id column."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260319_07"
down_revision = "20260319_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("products", "external_product_id")


def downgrade() -> None:
    op.add_column("products", sa.Column("external_product_id", sa.String(length=255), nullable=True))
