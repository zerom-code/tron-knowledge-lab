"""search runs and atomic quotas

Revision ID: b4dfad50a3d5
Revises: e866a381c7fe
Create Date: 2026-10-09 22:59:24.632348

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b4dfad50a3d5'
down_revision: Union[str, Sequence[str], None] = 'e866a381c7fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('rate_buckets',
    sa.Column('bucket', sa.String(length=100), nullable=False),
    sa.Column('used', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('bucket')
    )
    op.create_table('search_runs',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('search_runs')
    op.drop_table('rate_buckets')
