"""Populate reviews.search_vector using DB trigger and backfill existing rows."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260319_05"
down_revision = "20260318_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reviews_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.body, '')), 'B');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_reviews_search_vector_update ON reviews")
    op.execute(
        """
        CREATE TRIGGER trg_reviews_search_vector_update
        BEFORE INSERT OR UPDATE OF title, body
        ON reviews
        FOR EACH ROW
        EXECUTE FUNCTION reviews_search_vector_update();
        """
    )

    op.execute(
        """
        UPDATE reviews
        SET search_vector =
            setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(body, '')), 'B')
        WHERE search_vector IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reviews_search_vector_update ON reviews")
    op.execute("DROP FUNCTION IF EXISTS reviews_search_vector_update")
