"""knowledge model with provenance and vector indexes

Revision ID: 1de7eba65acc
Revises: 
Create Date: 2026-10-09 22:55:14.543746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy
from sqlalchemy.dialects import postgresql

revision: str = '1de7eba65acc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('projects',
    sa.Column('id', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('entities',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'name')
    )
    op.create_index(op.f('ix_entities_project_id'), 'entities', ['project_id'], unique=False)
    op.create_table('saved_examples',
    sa.Column('query', sa.Text(), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('query')
    )
    op.create_table('sources',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('snapshot_hash', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_project_id'), 'sources', ['project_id'], unique=False)
    op.create_table('topics',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'name')
    )
    op.create_index(op.f('ix_topics_project_id'), 'topics', ['project_id'], unique=False)
    op.create_table('assertions',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('topic_id', sa.String(length=100), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('checked_at', sa.Date(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.CheckConstraint("kind IN ('Fact', 'Claim')"),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assertions_project_id'), 'assertions', ['project_id'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('project_id', sa.String(length=40), nullable=False),
    sa.Column('source_id', sa.String(length=80), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('topic', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('live', sa.Boolean(), nullable=False),
    sa.Column('current_version_id', sa.String(length=100), nullable=True),
    sa.Column('updated', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_project_id'), 'documents', ['project_id'], unique=False)
    op.create_table('assertion_entities',
    sa.Column('assertion_id', sa.String(length=100), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=False),
    sa.ForeignKeyConstraint(['assertion_id'], ['assertions.id'], ),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ),
    sa.PrimaryKeyConstraint('assertion_id', 'entity_id')
    )
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('document_id', sa.String(length=80), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('document_versions',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('document_id', sa.String(length=80), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=40), nullable=False),
    sa.Column('raw_body', sa.Text(), nullable=False),
    sa.Column('body_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('change', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'number')
    )
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)
    op.create_table('sections',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('version_id', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['version_id'], ['document_versions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id', 'position')
    )
    op.create_index(op.f('ix_sections_version_id'), 'sections', ['version_id'], unique=False)
    op.create_table('chunks',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('document_id', sa.String(length=80), nullable=False),
    sa.Column('version_id', sa.String(length=100), nullable=False),
    sa.Column('section_id', sa.String(length=100), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('verification_note', sa.Text(), nullable=False),
    sa.Column('checked_at', sa.Date(), nullable=True),
    sa.Column('input_hash', sa.String(length=64), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=256), nullable=True),
    sa.Column('embedding_model', sa.String(length=80), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), sa.Computed("CASE WHEN language = 'RU' THEN to_tsvector('russian'::regconfig, text) ELSE to_tsvector('english'::regconfig, text) END", persisted=True), nullable=False),
    sa.CheckConstraint("status IN ('Verified', 'Unverified', 'Outdated')"),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ),
    sa.ForeignKeyConstraint(['version_id'], ['document_versions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chunks_document_id'), 'chunks', ['document_id'], unique=False)
    op.create_index('ix_chunks_embedding', 'chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('ix_chunks_fts', 'chunks', ['search_vector'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_chunks_version_id'), 'chunks', ['version_id'], unique=False)
    op.create_table('assertion_evidence',
    sa.Column('assertion_id', sa.String(length=100), nullable=False),
    sa.Column('chunk_id', sa.String(length=100), nullable=False),
    sa.Column('source_id', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['assertion_id'], ['assertions.id'], ),
    sa.ForeignKeyConstraint(['chunk_id'], ['chunks.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('assertion_id', 'chunk_id')
    )
    op.create_table('chunk_entities',
    sa.Column('chunk_id', sa.String(length=100), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=False),
    sa.ForeignKeyConstraint(['chunk_id'], ['chunks.id'], ),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ),
    sa.PrimaryKeyConstraint('chunk_id', 'entity_id')
    )
    op.create_foreign_key('fk_document_current_version', 'documents', 'document_versions', ['current_version_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_document_current_version', 'documents', type_='foreignkey')
    op.drop_table('chunk_entities')
    op.drop_table('assertion_evidence')
    op.drop_index(op.f('ix_chunks_version_id'), table_name='chunks')
    op.drop_index('ix_chunks_fts', table_name='chunks', postgresql_using='gin')
    op.drop_index('ix_chunks_embedding', table_name='chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index(op.f('ix_chunks_document_id'), table_name='chunks')
    op.drop_table('chunks')
    op.drop_index(op.f('ix_sections_version_id'), table_name='sections')
    op.drop_table('sections')
    op.drop_index(op.f('ix_document_versions_document_id'), table_name='document_versions')
    op.drop_table('document_versions')
    op.drop_table('audit_events')
    op.drop_table('assertion_entities')
    op.drop_index(op.f('ix_documents_project_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_assertions_project_id'), table_name='assertions')
    op.drop_table('assertions')
    op.drop_index(op.f('ix_topics_project_id'), table_name='topics')
    op.drop_table('topics')
    op.drop_index(op.f('ix_sources_project_id'), table_name='sources')
    op.drop_table('sources')
    op.drop_table('saved_examples')
    op.drop_index(op.f('ix_entities_project_id'), table_name='entities')
    op.drop_table('entities')
    op.drop_table('projects')
