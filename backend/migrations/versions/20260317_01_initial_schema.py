"""Initial Postgres schema baseline for ReviewLens backend."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260317_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # UUID defaults require pgcrypto for gen_random_uuid().
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False, server_default="capterra"),
        sa.Column("external_product_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "platform", "source_url", name="uq_products_workspace_platform_source_url"),
    )
    op.create_index("ix_products_workspace_id", "products", ["workspace_id"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("csv_filename", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.CheckConstraint("source_type IN ('scrape', 'csv_upload')", name="ck_ingestion_runs_source_type"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_ingestion_runs_status"),
    )
    op.create_index("ix_ingestion_runs_workspace_id", "ingestion_runs", ["workspace_id"])
    op.create_index("ix_ingestion_runs_product_id", "ingestion_runs", ["product_id"])
    op.create_index("ix_ingestion_runs_created_at", "ingestion_runs", ["created_at"])

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_platform", sa.String(length=50), nullable=False, server_default="capterra"),
        sa.Column("source_review_id", sa.String(length=255), nullable=True),
        sa.Column("review_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("reviewed_at", sa.Date(), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=8), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="SET NULL"),
        sa.CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_reviews_rating_range"),
        sa.UniqueConstraint("workspace_id", "product_id", "source_platform", "review_fingerprint", name="uq_reviews_dedup_fingerprint"),
    )
    op.create_index("ix_reviews_workspace_id", "reviews", ["workspace_id"])
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])
    op.create_index("ix_reviews_ingestion_run_id", "reviews", ["ingestion_run_id"])
    op.create_index("ix_reviews_reviewed_at", "reviews", ["reviewed_at"])
    op.create_index("ix_reviews_search_vector", "reviews", ["search_vector"], postgresql_using="gin")
    op.create_index(
        "uq_reviews_source_review_id_not_null",
        "reviews",
        ["workspace_id", "product_id", "source_platform", "source_review_id"],
        unique=True,
        postgresql_where=sa.text("source_review_id IS NOT NULL"),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_sessions_workspace_id", "chat_sessions", ["workspace_id"])
    op.create_index("ix_chat_sessions_product_id", "chat_sessions", ["product_id"])
    op.create_index("ix_chat_sessions_last_activity_at", "chat_sessions", ["last_activity_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("chat_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_refusal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('system', 'user', 'assistant')", name="ck_chat_messages_role"),
        sa.UniqueConstraint("chat_session_id", "message_index", name="uq_chat_messages_session_message_index"),
    )
    op.create_index("ix_chat_messages_chat_session_id", "chat_messages", ["chat_session_id"])
    op.create_index("ix_chat_messages_workspace_id", "chat_messages", ["workspace_id"])
    op.create_index("ix_chat_messages_product_id", "chat_messages", ["product_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_product_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_workspace_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_last_activity_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_product_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_workspace_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_index("uq_reviews_source_review_id_not_null", table_name="reviews")
    op.drop_index("ix_reviews_search_vector", table_name="reviews")
    op.drop_index("ix_reviews_reviewed_at", table_name="reviews")
    op.drop_index("ix_reviews_ingestion_run_id", table_name="reviews")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_reviews_workspace_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_ingestion_runs_created_at", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_product_id", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_workspace_id", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_index("ix_products_workspace_id", table_name="products")
    op.drop_table("products")

    op.drop_table("workspaces")
