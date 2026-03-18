"""Add unsupported_source outcome code to ingestion run constraints."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260318_03"
down_revision = "20260317_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_ingestion_runs_outcome_code", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_runs_outcome_code",
        "ingestion_runs",
        "outcome_code IS NULL OR outcome_code IN ('ok', 'low_data', 'blocked', 'parse_failed', 'unsupported_source', 'invalid_url', 'empty_csv', 'malformed_csv')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ingestion_runs_outcome_code", "ingestion_runs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_runs_outcome_code",
        "ingestion_runs",
        "outcome_code IS NULL OR outcome_code IN ('ok', 'low_data', 'blocked', 'parse_failed', 'invalid_url', 'empty_csv', 'malformed_csv')",
    )
