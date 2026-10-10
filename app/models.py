from datetime import date, datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db import Base


def now():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40), default="Website")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    snapshot_hash: Mapped[str] = mapped_column(String(64))


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    title: Mapped[str] = mapped_column(String(300))
    language: Mapped[str] = mapped_column(String(8), default="EN")
    topic: Mapped[str] = mapped_column(String(120), default="Resource model")
    status: Mapped[str] = mapped_column(String(20), default="Queued")
    live: Mapped[bool] = mapped_column(Boolean, default=True)
    current_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", use_alter=True, name="fk_document_current_version"), nullable=True,
    )
    updated: Mapped[date] = mapped_column(Date, default=date.today)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "number"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(40))
    raw_body: Mapped[str] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="Queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    change: Mapped[str] = mapped_column(Text, default="")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("version_id", "position"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    position: Mapped[int] = mapped_column(Integer)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint("status IN ('Verified', 'Unverified', 'Outdated')"),
        Index("ix_chunks_fts", "search_vector", postgresql_using="gin"),
        Index("ix_chunks_embedding", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("sections.id"))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(20), default="Unverified")
    verification_note: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list | None] = mapped_column(Vector(256), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR, Computed(
            "CASE WHEN language = 'RU' THEN to_tsvector('russian'::regconfig, text) "
            "ELSE to_tsvector('english'::regconfig, text) END", persisted=True,
        ),
    )


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("project_id", "name"),)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("project_id", "name"),)


class ChunkEntity(Base):
    __tablename__ = "chunk_entities"
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)


class Assertion(Base):
    __tablename__ = "assertions"
    __table_args__ = (CheckConstraint("kind IN ('Fact', 'Claim')"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="Unverified")
    checked_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")


class AssertionEvidence(Base):
    __tablename__ = "assertion_evidence"
    assertion_id: Mapped[str] = mapped_column(ForeignKey("assertions.id"), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))


class AssertionEntity(Base):
    __tablename__ = "assertion_entities"
    assertion_id: Mapped[str] = mapped_column(ForeignKey("assertions.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)


class SavedExample(Base):
    __tablename__ = "saved_examples"
    query: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    data: Mapped[dict] = mapped_column(JSONB)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="Queued")
    stage: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str] = mapped_column(String(60), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SearchRun(Base):
    __tablename__ = "search_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    bucket: Mapped[str] = mapped_column(String(100), primary_key=True)
    used: Mapped[int] = mapped_column(Integer)


class AnswerRun(Base):
    __tablename__ = "answer_runs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    search_run_id: Mapped[str] = mapped_column(ForeignKey("search_runs.id"), index=True)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
