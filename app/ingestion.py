import asyncio
import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from app import provider
from app.db import Session
from app.errors import AppError
from app.models import (
    Assertion, AssertionEntity, AssertionEvidence, AuditEvent, Chunk, ChunkEntity,
    Document, DocumentVersion, Entity, ProcessingJob, Section, Source, Topic, now,
)
from app.seed import entity_id, topic_id

ENTITIES = ["TRON", "USDT", "TRX", "Energy", "Bandwidth", "USDT TRC-20"]


def parse_article(body):
    if not body.strip():
        raise AppError("PARSING_ERROR", "Отсутствует обязательное поле body.")
    if "<" in body and ">" in body:
        soup = BeautifulSoup(body, "html.parser")
        for element in soup(["script", "style", "nav", "footer"]):
            element.decompose()
        body = soup.get_text("\n\n", strip=True)
    if not body.strip():
        raise AppError("PARSING_ERROR", "В статье нет текста после очистки HTML.")
    parts = []
    title = "Основной текст"
    for paragraph in re.split(r"\n\s*\n", body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if paragraph.startswith("#"):
            title = paragraph.lstrip("#").strip()[:300] or "Раздел"
            continue
        while paragraph:
            if len(paragraph) <= 1000:
                piece, paragraph = paragraph, ""
            else:
                split = paragraph.rfind(" ", 0, 1000)
                split = split if split > 300 else 1000
                piece, paragraph = paragraph[:split], paragraph[split:].lstrip()
            parts.append((title, piece))
    if not parts:
        raise AppError("PARSING_ERROR", "Не найдены абзацы статьи.")
    if len(parts) > 12:
        raise AppError("CHUNK_LIMIT", "Более 12 chunks. Сократите статью.")
    return parts


async def create_document(session, request, document_id=None):
    existing = None
    if document_id:
        existing = await session.scalar(select(Document).where(
            Document.id == document_id, Document.project_id == "tpe").with_for_update())
        if not existing:
            raise AppError("NOT_FOUND", "Документ не найден.", 404)
        pending = await session.scalar(select(ProcessingJob).where(
            ProcessingJob.document_id == document_id,
            ProcessingJob.status.in_(["Queued", "Processing"])))
        if pending:
            raise AppError("ALREADY_PROCESSING", "Дождитесь текущей обработки.", 409)
    did = document_id or "DOC-" + uuid.uuid4().hex[:12]
    vid = "VER-" + uuid.uuid4().hex
    digest = hashlib.sha256(request.body.encode()).hexdigest()
    if not existing:
        sid = "SRC-" + uuid.uuid4().hex[:12]
        session.add(Source(id=sid, project_id="tpe", name="Загруженная статья",
                           url=str(request.url), kind="Submitted text", snapshot_hash=digest))
        await session.flush()
        existing = Document(
            id=did, project_id="tpe", source_id=sid, title=request.title,
            language=request.language, topic=request.topic, status="Queued", live=True,
        )
        session.add(existing)
        await session.flush()
    else:
        source = await session.get(Source, existing.source_id)
        if source.url != str(request.url):
            raise AppError("SOURCE_CHANGED", "При повторе используйте тот же URL источника.", 409)
    versions = list((await session.scalars(select(DocumentVersion).where(
        DocumentVersion.document_id == did))).all())
    number = max((v.number for v in versions), default=0) + 1
    version = DocumentVersion(
        id=vid, document_id=did, number=number, label=str(number) + "-" + digest[:6],
        raw_body=request.body, body_hash=digest,
        change="Загружен текст; проверка достоверности выполняется отдельно.",
    )
    session.add(version)
    await session.flush()
    if not existing.current_version_id:
        existing.current_version_id = vid
    existing.status = "Queued"
    session.add(ProcessingJob(id="JOB-" + uuid.uuid4().hex, document_id=did, version_id=vid))
    session.add(AuditEvent(document_id=did, action="Queued", details={"version_id": vid}))
    await session.commit()
    return {"documentId": did, "versionId": vid, "status": "Queued"}


async def stage(job_id, number):
    async with Session.begin() as session:
        job = await session.get(ProcessingJob, job_id)
        job.stage = number
        job.updated_at = now()
        session.add(AuditEvent(document_id=job.document_id, action="Processing",
                               details={"stage": number, "version_id": job.version_id}))


async def process(job_id):
    try:
        await stage(job_id, 1)
        async with Session() as session:
            job = await session.get(ProcessingJob, job_id)
            version = await session.get(DocumentVersion, job.version_id)
            doc = await session.get(Document, job.document_id)
            parts = parse_article(version.raw_body)
            vid, did, language, topic, sid = version.id, doc.id, doc.language, doc.topic, doc.source_id
        await stage(job_id, 2)
        async with Session.begin() as session:
            # A resumed job replaces only its own incomplete data.
            old_ids = list((await session.scalars(select(Chunk.id).where(Chunk.version_id == vid))).all())
            old_assertions = list((await session.scalars(select(AssertionEvidence.assertion_id).where(
                AssertionEvidence.chunk_id.in_(old_ids)))).all())
            await session.execute(delete(AssertionEntity).where(AssertionEntity.assertion_id.in_(old_assertions)))
            await session.execute(delete(AssertionEvidence).where(AssertionEvidence.assertion_id.in_(old_assertions)))
            await session.execute(delete(Assertion).where(Assertion.id.in_(old_assertions)))
            await session.execute(delete(ChunkEntity).where(ChunkEntity.chunk_id.in_(old_ids)))
            await session.execute(delete(Chunk).where(Chunk.version_id == vid))
            await session.execute(delete(Section).where(Section.version_id == vid))
            section_positions = []
            headings = []
            for heading, _ in parts:
                if not headings or headings[-1] != heading:
                    headings.append(heading)
                section_positions.append(len(headings) - 1)
            for i, heading in enumerate(headings):
                session.add(Section(id=vid + "-SEC-" + str(i), version_id=vid, title=heading, position=i))
            await session.flush()
            for i, (_, text) in enumerate(parts):
                session.add(Chunk(
                    id=vid + "-CHK-" + str(i), document_id=did, version_id=vid,
                    section_id=vid + "-SEC-" + str(section_positions[i]), position=i, text=text, language=language,
                    status="Unverified", input_hash=hashlib.sha256(text.encode()).hexdigest(),
                    verification_note="Текст загружен редактором; нужна сверка с источником.",
                ))
        await stage(job_id, 3)
        await stage(job_id, 4)
        async with Session.begin() as session:
            await session.execute(insert(Topic).values(
                id=topic_id(topic), project_id="tpe", name=topic).on_conflict_do_nothing())
            chunks = list((await session.scalars(select(Chunk).where(Chunk.version_id == vid))).all())
            for c in chunks:
                aid = c.id + "-CLAIM"
                session.add(Assertion(id=aid, project_id="tpe", topic_id=topic_id(topic),
                                      text=c.text, kind="Claim", status="Unverified",
                                      reason="Выдержка-кандидат. Требуется проверка редактором."))
                await session.flush()
                session.add(AssertionEvidence(assertion_id=aid, chunk_id=c.id, source_id=sid))
                for name in ENTITIES:
                    if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", c.text, re.I):
                        await session.execute(insert(Entity).values(
                            id=entity_id(name), project_id="tpe", name=name).on_conflict_do_nothing())
                        session.add(ChunkEntity(chunk_id=c.id, entity_id=entity_id(name)))
                        session.add(AssertionEntity(assertion_id=aid, entity_id=entity_id(name)))
        await stage(job_id, 5)
        for i, (_, text) in enumerate(parts):
            cid = vid + "-CHK-" + str(i)
            digest = hashlib.sha256(text.encode()).hexdigest()
            async with Session() as session:
                cached = await session.scalar(select(Chunk).where(
                    Chunk.input_hash == digest, Chunk.embedding.is_not(None),
                    Chunk.embedding_model == "text-embedding-3-small").limit(1))
                vector = cached.embedding.tolist() if cached is not None else None
            vector = vector if vector is not None else await provider.embed(text)
            async with Session.begin() as session:
                chunk = await session.get(Chunk, cid)
                chunk.embedding = vector
                chunk.embedding_model = "text-embedding-3-small"
                job = await session.get(ProcessingJob, job_id)
                job.updated_at = now()
        await stage(job_id, 6)
        async with Session.begin() as session:
            job = await session.get(ProcessingJob, job_id)
            version = await session.get(DocumentVersion, vid)
            document = await session.get(Document, did)
            version.status = "Processed"
            document.current_version_id = vid
            document.status = "Processed"
            document.updated = date.today()
            source = await session.get(Source, document.source_id)
            source.snapshot_hash = version.body_hash
            source.fetched_at = now()
            job.status = "Processed"
            job.stage = 7
            job.updated_at = now()
            session.add(AuditEvent(document_id=did, action="Processed", details={"version_id": vid}))
    except asyncio.CancelledError:
        async with Session.begin() as session:
            job = await session.get(ProcessingJob, job_id)
            job.status = "Queued"
        raise
    except Exception as error:
        known = isinstance(error, AppError)
        async with Session.begin() as session:
            job = await session.get(ProcessingJob, job_id)
            job.status = "Failed"
            job.error_code = error.code if known else "PROCESSING_ERROR"
            job.error_message = error.message if known else "Не удалось обработать статью. Повторите запуск."
            job.updated_at = now()
            version = await session.get(DocumentVersion, job.version_id)
            version.status = "Failed"
            doc = await session.get(Document, job.document_id)
            doc.status = "Failed"
            session.add(AuditEvent(document_id=doc.id, action="Failed",
                                   details={"code": job.error_code, "stage": job.stage}))


async def worker_loop():
    while True:
        async with Session.begin() as session:
            job = await session.scalar(select(ProcessingJob).where(
                (ProcessingJob.status == "Queued") |
                ((ProcessingJob.status == "Processing") &
                 (ProcessingJob.updated_at < now() - timedelta(minutes=3)))
            ).order_by(ProcessingJob.updated_at).with_for_update(skip_locked=True).limit(1))
            job_id = job.id if job else None
            if job:
                job.status = "Processing"
                job.updated_at = now()
                version = await session.get(DocumentVersion, job.version_id)
                version.status = "Processing"
                doc = await session.get(Document, job.document_id)
                doc.status = "Processing"
        if job_id:
            await process(job_id)
        else:
            await asyncio.sleep(0.5)
