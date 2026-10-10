"""persist grounded answers

Revision ID: 8e8bc5524150
Revises: b4dfad50a3d5
Create Date: 2026-10-09 23:02:04.195792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '8e8bc5524150'
down_revision: Union[str, Sequence[str], None] = 'b4dfad50a3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('answer_runs',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('search_run_id', sa.String(length=80), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['search_run_id'], ['search_runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_answer_runs_search_run_id'), 'answer_runs', ['search_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_answer_runs_search_run_id'), table_name='answer_runs')
    op.drop_table('answer_runs')
