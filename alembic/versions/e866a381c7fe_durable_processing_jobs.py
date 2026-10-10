"""durable processing jobs

Revision ID: e866a381c7fe
Revises: 1de7eba65acc
Create Date: 2026-10-09 22:56:51.754399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e866a381c7fe'
down_revision: Union[str, Sequence[str], None] = '1de7eba65acc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('processing_jobs',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('document_id', sa.String(length=80), nullable=False),
    sa.Column('version_id', sa.String(length=100), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('stage', sa.Integer(), nullable=False),
    sa.Column('error_code', sa.String(length=60), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['version_id'], ['document_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id')
    )
    op.create_index(op.f('ix_processing_jobs_document_id'), 'processing_jobs', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_processing_jobs_document_id'), table_name='processing_jobs')
    op.drop_table('processing_jobs')
