import json
import math
from datetime import timedelta
from sqlalchemy import select
from app.errors import AppError
from app.models import Chunk, SearchRun, now
from app.rag import prefiltered
from app.repository import snapshot
from app.schemas import Filters

MAX_CHUNKS = 6
MAX_CHARS = 7800
MIN_RELEVANCE = .7


def choose(corpus, result):
    candidates = [c for c in result["items"] if c["status"] == "Verified" and c["score"] >= MIN_RELEVANCE]
    selected, facts, docs = [], set(), set()
    while candidates and len(selected) < MAX_CHUNKS:
        def gain(c):
            new = [f for f in corpus["facts"] if f["status"] == "Verified"
                   and c["id"] in f["chunkIds"] and f["id"] not in facts]
            return c["score"] + .12 * len(new) + (0 if c["documentId"] in docs else .05)
        candidates.sort(key=lambda c: (-gain(c), -c["rrf"], c["id"]))
        c = candidates.pop(0)
        selected.append(c["id"])
        docs.add(c["documentId"])
        facts.update(f["id"] for f in corpus["facts"] if c["id"] in f["chunkIds"])
    return selected


async def get_run(session, run_id):
    run = await session.get(SearchRun, run_id)
    if not run or run.project_id != "tpe":
        raise AppError("UNKNOWN_RUN", "Поиск не найден. Выполните новый запрос.", 404)
    if run.created_at < now() - timedelta(hours=2):
        raise AppError("STALE_RUN", "Результаты поиска устарели. Выполните новый запрос.", 409)
    return run.result


async def build(session, result, selected_ids):
    known = {c["id"]: c for c in result["items"]}
    if len(selected_ids) > MAX_CHUNKS or len(selected_ids) != len(set(selected_ids)):
        raise AppError("INVALID_SELECTION", "Выберите не более шести разных chunks.", 422)
    if any(cid not in known for cid in selected_ids):
        raise AppError("INVALID_SELECTION", "Выбранный chunk отсутствует в результатах поиска.", 422)
    corpus = await snapshot(session)
    docs = {d["id"]: d for d in corpus["documents"]}
    available = set((await session.scalars(prefiltered(Filters(**result["filters"]))
                                          .with_only_columns(Chunk.id))).all())
    current = {c["id"]: c for c in corpus["chunks"]}
    chunks, exclusions, chars = [], [], 0
    selected = set(selected_ids)
    for candidate in result["items"]:
        cid = candidate["id"]
        c = current.get(cid)
        reason = None
        if cid not in available or not c or docs[c["documentId"]]["versionId"] != candidate["versionId"]:
            reason = "Версия или статус индекса изменились; выполните новый поиск"
        elif c["status"] != "Verified":
            reason = "Не подтверждён источником"
        elif not candidate["scored"]:
            reason = "Релевантность не оценена"
        elif candidate["score"] < MIN_RELEVANCE:
            reason = "Недостаточная релевантность"
        elif cid not in selected:
            reason = "Не выбран"
        elif len(chunks) >= MAX_CHUNKS or chars + len(c["text"]) > MAX_CHARS:
            reason = "Лимит контекста"
        if reason:
            exclusions.append({"id": cid, "reason": reason})
        else:
            chunks.append({**candidate, **c})
            chars += len(c["text"])
    ids = {c["id"] for c in chunks}
    facts = []
    for fact in corpus["facts"]:
        evidence = [cid for cid in fact["chunkIds"] if cid in ids]
        source_ids = sorted({docs[current[cid]["documentId"]]["sourceId"] for cid in evidence}
                            & set(fact["sourceIds"]))
        if fact["status"] == "Verified" and evidence and source_ids:
            facts.append({**fact, "chunkIds": evidence, "sourceIds": source_ids})
    source_ids = {docs[c["documentId"]]["sourceId"] for c in chunks}
    sources = [s for s in corpus["sources"] if s["id"] in source_ids]
    reasons = []
    if not result["info"]["supported"]:
        reasons.append("Вопрос выходит за рамки материалов базы.")
    if result["info"]["future"]:
        reasons.append("В источниках нет прогноза точной комиссии на будущую дату.")
    elif result["info"]["exactAmount"]:
        reasons.append("Для точной комиссии нужны параметры транзакции и текущее состояние сети.")
    if not result["coverage"]:
        reasons.append(result["coverageReason"])
    if len(chunks) < 2:
        reasons.append("Нужно выбрать как минимум два релевантных проверенных фрагмента.")
    if len(facts) < 2:
        reasons.append("Недостаточно фактов, подтверждённых выбранными фрагментами.")
    if not sources:
        reasons.append("Нет подтверждённых источников выбранных фрагментов.")
    payload = {
        "project_id": "tpe", "question": result["query"],
        "chunks": [{
            "id": c["id"], "document_id": c["documentId"], "version": c["version"],
            "text": c["text"], "source_id": docs[c["documentId"]]["sourceId"],
            "verification_status": c["status"], "relevance_score": c["score"],
        } for c in chunks],
        "facts": [{
            "id": f["id"], "text": f["text"], "status": f["status"],
            "evidence_chunk_ids": f["chunkIds"], "source_ids": f["sourceIds"],
        } for f in facts],
        "sources": [{
            "id": s["id"], "name": s["name"], "title": s["title"], "url": s["url"],
            "document_id": s["documentId"], "snapshot_date": s["date"],
            "snapshot_hash": s["snapshotHash"],
        } for s in sources],
        "confidence": {
            "level": "Low" if reasons else "Sufficient",
            "policy": "query coverage; >=2 Verified chunks with rerank >=0.7; >=2 supported facts; source provenance",
            "reasons": reasons,
        },
    }
    return {
        "chunks": chunks, "facts": facts, "sources": sources, "ok": not reasons,
        "reasons": reasons, "payload": payload, "exclusions": exclusions,
        "estimatedTokens": math.ceil(len(json.dumps(payload, ensure_ascii=False)) / 3),
        "textChars": chars, "maxTextChars": MAX_CHARS,
    }
