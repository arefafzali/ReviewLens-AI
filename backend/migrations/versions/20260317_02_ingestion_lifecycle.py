"""Update ingestion run lifecycle status and outcome metadata columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260317_02"
down_revision = "20260317_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_ingestion_runs_status", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_runs_status",
        "ingestion_runs",
        "status IN ('running', 'success', 'partial', 'failed')",
    )

    op.alter_column("ingestion_runs", "status", server_default="running")

    op.add_column("ingestion_runs", sa.Column("outcome_code", sa.String(length=32), nullable=True))
    op.add_column(
        "ingestion_runs",
        sa.Column("records_ingested", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("ingestion_runs", sa.Column("error_detail", sa.Text(), nullable=True))
    op.add_column(
        "ingestion_runs",
        sa.Column(
            "result_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_check_constraint(
        "ck_ingestion_runs_outcome_code",
        "ingestion_runs",
        "outcome_code IS NULL OR outcome_code IN ('ok', 'low_data', 'blocked', 'parse_failed', 'invalid_url', 'empty_csv', 'malformed_csv')",
    )

    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_outcome_code", "ingestion_runs", ["outcome_code"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_outcome_code", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")

    op.drop_constraint("ck_ingestion_runs_outcome_code", "ingestion_runs", type_="check")

    op.drop_column("ingestion_runs", "result_metadata")
    op.drop_column("ingestion_runs", "error_detail")
    op.drop_column("ingestion_runs", "records_ingested")
    op.drop_column("ingestion_runs", "outcome_code")

    op.drop_constraint("ck_ingestion_runs_status", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_runs_status",
        "ingestion_runs",
        "status IN ('queued', 'running', 'succeeded', 'failed')",
    )
    op.alter_column("ingestion_runs", "status", server_default="queued")
