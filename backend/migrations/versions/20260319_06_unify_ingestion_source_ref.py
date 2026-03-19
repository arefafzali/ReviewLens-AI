"""Unify ingestion run source reference by dropping legacy csv_filename column."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260319_06"
down_revision = "20260319_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("ingestion_runs", "csv_filename")


def downgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("csv_filename", sa.String(length=255), nullable=True))
