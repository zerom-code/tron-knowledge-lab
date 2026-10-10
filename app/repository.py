from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Assertion, AssertionEntity, AssertionEvidence, Chunk, ChunkEntity,
    Document, DocumentVersion, Entity, ProcessingJob, Section, Source, Topic,
)


async def snapshot(session: AsyncSession, project_id="tpe"):
    docs = list((await session.scalars(select(Document).where(
        Document.project_id == project_id).order_by(Document.created_at, Document.id))).all())
    ids = [d.id for d in docs]
    sources = list((await session.scalars(select(Source).where(Source.project_id == project_id))).all())
    versions = list((await session.scalars(select(DocumentVersion).where(
        DocumentVersion.document_id.in_(ids)).order_by(DocumentVersion.number.desc()))).all())
    current_ids = [d.current_version_id for d in docs if d.current_version_id]
    jobs = list((await session.scalars(select(ProcessingJob).where(
        ProcessingJob.document_id.in_(ids)).order_by(ProcessingJob.updated_at.desc()))).all())
    sections = list((await session.scalars(select(Section).where(
        Section.version_id.in_(current_ids)).order_by(Section.position))).all())
    chunks = list((await session.scalars(select(Chunk).where(
        Chunk.version_id.in_(current_ids)).order_by(Chunk.position, Chunk.id))).all())
    entity_names = {e.id: e.name for e in (await session.scalars(
        select(Entity).where(Entity.project_id == project_id))).all()}
    topic_names = {t.id: t.name for t in (await session.scalars(
        select(Topic).where(Topic.project_id == project_id))).all()}
    chunk_entities = defaultdict(list)
    for link in (await session.scalars(select(ChunkEntity).where(
        ChunkEntity.chunk_id.in_([c.id for c in chunks])))).all():
        chunk_entities[link.chunk_id].append(entity_names[link.entity_id])
    assertions = list((await session.scalars(select(Assertion).where(
        Assertion.project_id == project_id).order_by(Assertion.id))).all())
    evidence = defaultdict(list)
    for link in (await session.scalars(select(AssertionEvidence).where(
        AssertionEvidence.assertion_id.in_([a.id for a in assertions])))).all():
        evidence[link.assertion_id].append(link)
    assertion_entities = defaultdict(list)
    for link in (await session.scalars(select(AssertionEntity).where(
        AssertionEntity.assertion_id.in_([a.id for a in assertions])))).all():
        assertion_entities[link.assertion_id].append(entity_names[link.entity_id])
    source_map = {s.id: s for s in sources}
    version_map = {v.id: v for v in versions}
    current_chunks = {c.id for c in chunks}
    source_documents = {d.source_id: d for d in docs}
    output = {
        "projectId": project_id,
        "defaultQuery": "How can I reduce USDT TRC-20 transaction fees?",
        "lowQuery": "What exact fee will I pay for a USDT TRC-20 transfer tomorrow?",
        "embeddingModel": "text-embedding-3-small", "embeddingDimensions": 256,
        "documents": [], "chunks": [], "facts": [], "claims": [], "sources": [],
    }
    for s in sources:
        d = source_documents.get(s.id)
        output["sources"].append({
            "id": s.id, "name": s.name, "title": d.title if d else s.name,
            "url": s.url, "external": True, "type": s.kind,
            "date": s.fetched_at.date().isoformat(), "fetchedAt": s.fetched_at.isoformat(),
            "snapshotHash": s.snapshot_hash, "documentId": d.id if d else "",
        })
    for d in docs:
        v = version_map.get(d.current_version_id)
        ds = [s for s in sections if s.version_id == d.current_version_id]
        dc = [c for c in chunks if c.document_id == d.id]
        output["documents"].append({
            "id": d.id, "projectId": d.project_id, "title": d.title,
            "source": source_map[d.source_id].name, "sourceId": d.source_id,
            "url": source_map[d.source_id].url, "language": d.language,
            "status": d.status, "updated": d.updated.isoformat(),
            "version": v.label if v else "—", "versionId": d.current_version_id,
            "live": d.live, "embedded": sum(c.embedding is not None for c in dc),
            "topic": d.topic, "entities": sorted({e for c in dc for e in chunk_entities[c.id]}),
            "sections": [{"id": s.id, "title": s.title,
                          "chunks": [c.id for c in dc if c.section_id == s.id]} for s in ds],
            "history": [{"version": h.label, "date": h.created_at.date().isoformat(), "status": h.status,
                         "live": h.id == d.current_version_id and d.live,
                         "change": h.change} for h in versions if h.document_id == d.id],
            "searchable": bool(v and v.status == "Processed" and d.live),
        })
        job = next((j for j in jobs if j.document_id == d.id), None)
        if job:
            item = output["documents"][-1]
            pending_version = version_map[job.version_id]
            item.update({
                "job": {"id": job.id, "stage": job.stage, "status": job.status,
                        "version": pending_version.label},
                "rawBody": pending_version.raw_body,
                "failedStage": job.stage,
                "error": (job.error_code + ": " + job.error_message) if job.error_code else "",
            })
    for c in chunks:
        output["chunks"].append({
            "id": c.id, "documentId": c.document_id, "sectionId": c.section_id,
            "text": c.text, "status": c.status, "entities": chunk_entities[c.id],
            "inputHash": c.input_hash, "verificationNote": c.verification_note,
        })
    for a in assertions:
        links = [link for link in evidence[a.id] if link.chunk_id in current_chunks]
        if not links:
            continue
        item = {
            "id": a.id, "text": a.text, "status": a.status,
            "chunkIds": [link.chunk_id for link in links],
            "sourceIds": sorted({link.source_id for link in links}),
            "entities": assertion_entities[a.id], "topic": topic_names[a.topic_id],
            "checkedAt": a.checked_at.isoformat() if a.checked_at else None, "reason": a.reason,
        }
        output["facts" if a.kind == "Fact" else "claims"].append(item)
    return output
