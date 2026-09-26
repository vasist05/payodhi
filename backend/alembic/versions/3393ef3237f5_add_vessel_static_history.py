"""add_vessel_static_history

Revision ID: 3393ef3237f5
Revises: fb8eca0547d6
Create Date: 2026-09-22 10:06:02.702260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3393ef3237f5'
down_revision: Union[str, Sequence[str], None] = 'fb8eca0547d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'vessel_static_history',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('vessel_id', sa.UUID(), nullable=False),
        sa.Column('recorded_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('draft_meters', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('destination', sa.Text(), nullable=True),
        sa.Column('eta', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('dimension_length', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('dimension_beam', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('draft_meters IS NULL OR draft_meters >= 0', name='chk_vessel_static_history_draft'),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessels.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vessel_static_history_vessel_time', 'vessel_static_history', ['vessel_id', sa.literal_column('recorded_at DESC')])
    op.create_index('idx_vessel_static_history_recorded_at', 'vessel_static_history', ['recorded_at'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_vessel_static_history_recorded_at', table_name='vessel_static_history')
    op.drop_index('idx_vessel_static_history_vessel_time', table_name='vessel_static_history')
    op.drop_table('vessel_static_history')

