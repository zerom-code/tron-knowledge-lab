from contextlib import asynccontextmanager
import asyncio
from urllib.parse import urlsplit
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import ROOT, settings
from app.db import engine, get_session
from app.repository import snapshot
from app.seed import seed
from app.ingestion import create_document, worker_loop
from app.models import Assertion, AssertionEvidence, AuditEvent, Chunk, Document, DocumentVersion
from app.schemas import ArticleInput, ContextInput, LiveInput, SearchInput, VerificationInput
from app.security import editor, editor_configured
from app.errors import AppError
from app.quotas import reserve
from app.rag import search
from app.context import MAX_CHARS, MAX_CHUNKS, MIN_RELEVANCE, build, choose, get_run
from app.agent import answer
from datetime import date


@asynccontextmanager
async def lifespan(app):
    await seed()
    worker = asyncio.create_task(worker_loop())
    yield
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(title="TRON Knowledge Lab — Python API", version="3.1.0", lifespan=lifespan)


@app.exception_handler(AppError)
async def app_error(request, error):
    return JSONResponse({"error": {"code": error.code, "message": error.message}},
                        status_code=error.status)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    fields = [".".join(map(str, entry["loc"][1:])) for entry in error.errors()[:5]]
    return JSONResponse({"error": {
        "code": "INVALID_REQUEST",
        "message": "Проверьте поля запроса: " + ", ".join(fields),
    }}, status_code=422)


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    return JSONResponse({"error": {
        "code": "INTERNAL_ERROR", "message": "Не удалось завершить действие на сервере. Повторите позже.",
    }}, status_code=500)


@app.middleware("http")
async def safe_requests(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and (urlsplit(origin).netloc != request.url.netloc
                       or urlsplit(origin).scheme not in ("http", "https")):
            return JSONResponse({"error": {"code": "ORIGIN_NOT_ALLOWED",
                                "message": "Откройте интерфейс и API по одному адресу."}}, status_code=403)
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 24000:
                return JSONResponse({"error": {"code": "REQUEST_TOO_LARGE",
                                    "message": "Слишком большой запрос."}}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    vector_version = await session.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
    return {
        "ready": bool(vector_version), "backend": "Python / FastAPI",
        "database": "PostgreSQL", "pgvector": vector_version,
        "liveAvailable": bool(settings.openai_api_key.get_secret_value()),
        "editorConfigured": editor_configured(),
        "defaultMode": settings.ai_mode,
        "limits": {"relevance": MIN_RELEVANCE, "selected": MAX_CHUNKS, "contextChars": MAX_CHARS},
    }


@app.post("/api/editor/check", dependencies=[Depends(editor)])
async def check_editor():
    return {"authenticated": True}


@app.get("/api/bootstrap")
async def bootstrap(session: AsyncSession = Depends(get_session)):
    return await snapshot(session)


@app.post("/api/documents", dependencies=[Depends(editor)], status_code=202)
async def import_article(request: Request, data: ArticleInput, session: AsyncSession = Depends(get_session)):
    await reserve(request)
    return await create_document(session, data)


@app.post("/api/documents/{document_id}/retry", dependencies=[Depends(editor)], status_code=202)
async def retry_article(request: Request, document_id: str, data: ArticleInput, session: AsyncSession = Depends(get_session)):
    await reserve(request)
    return await create_document(session, data, document_id)


@app.post("/api/documents/{document_id}/live", dependencies=[Depends(editor)])
async def document_live(document_id: str, data: LiveInput, session: AsyncSession = Depends(get_session)):
    doc = await session.scalar(select(Document).where(Document.id == document_id, Document.project_id == "tpe"))
    if not doc:
        raise AppError("NOT_FOUND", "Документ не найден.", 404)
    doc.live = data.live
    session.add(AuditEvent(document_id=doc.id, action="Live changed", details={"live": data.live}))
    await session.commit()
    return {"live": doc.live}


@app.post("/api/search")
async def rag_search(request: Request, data: SearchInput, session: AsyncSession = Depends(get_session)):
    result = await search(session, data, lambda: reserve(request))
    corpus = await snapshot(session)
    selection = choose(corpus, result)
    # For the original real example, preserve its checked evidence when still eligible.
    if data.mode == "saved":
        from app.models import SavedExample
        example = await session.get(SavedExample, data.query)
        if example:
            eligible_ids = {c["id"] for c in result["items"]
                            if c["status"] == "Verified" and c["score"] >= MIN_RELEVANCE}
            selection = [cid for cid in example.data["selection"] if cid in eligible_ids]
    return {**result, "selected_ids": selection, "context": await build(session, result, selection)}


@app.post("/api/context")
async def context_builder(data: ContextInput, session: AsyncSession = Depends(get_session)):
    result = await get_run(session, data.run_id)
    return await build(session, result, data.selected_ids)


@app.post("/api/answer")
async def ai_answer(request: Request, data: ContextInput, session: AsyncSession = Depends(get_session)):
    result = await get_run(session, data.run_id)
    context = await build(session, result, data.selected_ids)
    return await answer(session, result, context, lambda: reserve(request))


@app.post("/api/chunks/{chunk_id}/verify", dependencies=[Depends(editor)])
async def verify_chunk(chunk_id: str, data: VerificationInput, session: AsyncSession = Depends(get_session)):
    chunk = await session.scalar(select(Chunk).join(Document, Chunk.document_id == Document.id).where(
        Chunk.id == chunk_id, Document.project_id == "tpe", Chunk.version_id == Document.current_version_id))
    if not chunk:
        raise AppError("NOT_FOUND", "Текущий chunk не найден.", 404)
    chunk.status = "Verified"
    chunk.verification_note = data.note
    chunk.checked_at = date.today()
    assertions = (await session.scalars(select(Assertion).join(
        AssertionEvidence, AssertionEvidence.assertion_id == Assertion.id).where(
            AssertionEvidence.chunk_id == chunk.id))).all()
    for assertion in assertions:
        if assertion.kind == "Claim" and assertion.text == chunk.text:
            assertion.kind = "Fact"
            assertion.status = "Verified"
            assertion.checked_at = date.today()
            assertion.reason = "Редактор сверил выдержку с источником: " + data.note
    session.add(AuditEvent(document_id=chunk.document_id, action="Verified",
                           details={"chunk_id": chunk.id, "note": data.note}))
    await session.commit()
    return {"id": chunk.id, "status": "Verified"}


@app.get("/api/metadata")
async def metadata(session: AsyncSession = Depends(get_session)):
    corpus = await snapshot(session)
    return {
        "languages": sorted({d["language"] for d in corpus["documents"]}),
        "sources": sorted({s["name"] for s in corpus["sources"]}),
        "topics": sorted({d["topic"] for d in corpus["documents"]}),
        "entities": sorted({e for c in corpus["chunks"] for e in c["entities"]}),
        "documents": [{"id": d["id"], "title": d["title"]} for d in corpus["documents"]],
        "verification": ["Verified", "Unverified", "Outdated"],
        "project": "tpe", "dateSemantics": "snapshot_received_since",
    }


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="interface")
