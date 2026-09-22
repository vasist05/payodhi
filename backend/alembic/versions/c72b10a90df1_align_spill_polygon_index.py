"""align_spill_polygon_index

Revision ID: c72b10a90df1
Revises: fb8eca0547d6
Create Date: 2026-09-21 23:45:00.000000

Aligns spill polygon spatial index name with DataBaseFinal.md §5 contract (idx_spills_polygon).
Does not modify columns or existing migrations.
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'c72b10a90df1'
down_revision: Union[str, Sequence[str], None] = 'fb8eca0547d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure idx_spills_polygon exists exactly per DataBaseFinal.md §5."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_spills_spill_polygon') THEN
                ALTER INDEX idx_spills_spill_polygon RENAME TO idx_spills_polygon;
            ELSIF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_spills_polygon') THEN
                CREATE INDEX idx_spills_polygon ON spills USING gist (spill_polygon);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Revert index name alignment."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_spills_polygon') THEN
                ALTER INDEX idx_spills_polygon RENAME TO idx_spills_spill_polygon;
            END IF;
        END $$;
    """)
