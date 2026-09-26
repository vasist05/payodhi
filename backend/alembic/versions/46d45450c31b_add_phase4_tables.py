"""add_phase4_tables

Revision ID: 46d45450c31b
Revises: c72b10a90df1
Create Date: 2026-09-22 23:49:10.687221

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '46d45450c31b'
down_revision: Union[str, Sequence[str], None] = ('3393ef3237f5', 'c72b10a90df1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('sar_targets',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('scene_id', sa.UUID(), nullable=False),
        sa.Column('detected_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('position', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
        sa.Column('intensity', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column('patch_uri', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='chk_sar_targets_confidence'),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sar_targets_scene', 'sar_targets', ['scene_id'])
    op.create_index('idx_sar_targets_position', 'sar_targets', ['position'], postgresql_using='gist')
    op.create_index('idx_sar_targets_detected_at', 'sar_targets', ['detected_at'])

    op.create_table('target_correlations',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('sar_target_id', sa.UUID(), nullable=False),
        sa.Column('vessel_id', sa.UUID(), nullable=True),
        sa.Column('match_status', sa.Enum('matched', 'dark_vessel', 'borderline', name='match_status_enum'), nullable=False),
        sa.Column('haversine_distance_m', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('anomaly_flags', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "(match_status = 'dark_vessel' AND vessel_id IS NULL) OR "
            "(match_status = 'matched' AND vessel_id IS NOT NULL) OR "
            "(match_status = 'borderline')",
            name='chk_target_correlations_status_vessel'
        ),
        sa.ForeignKeyConstraint(['sar_target_id'], ['sar_targets.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['vessel_id'], ['vessels.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sar_target_id', name='uq_target_correlations_sar_target')
    )
    op.create_index('idx_target_correlations_vessel', 'target_correlations', ['vessel_id'])
    op.create_index('idx_target_correlations_status', 'target_correlations', ['match_status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_target_correlations_status', table_name='target_correlations')
    op.drop_index('idx_target_correlations_vessel', table_name='target_correlations')
    op.drop_table('target_correlations')
    op.drop_index('idx_sar_targets_detected_at', table_name='sar_targets')
    op.drop_index('idx_sar_targets_position', table_name='sar_targets', postgresql_using='gist')
    op.drop_index('idx_sar_targets_scene', table_name='sar_targets')
    op.drop_table('sar_targets')
    op.execute("DROP TYPE IF EXISTS match_status_enum")
