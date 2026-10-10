import hashlib
import json
from datetime import date, datetime, timezone
from app.config import ROOT
from app.db import Session
from app.models import (
    Assertion, AssertionEntity, AssertionEvidence, Chunk, ChunkEntity, Document,
    DocumentVersion, Entity, Project, SavedExample, Section, Source, Topic,
)


def entity_id(name):
    return "ENT-" + hashlib.sha256(name.encode()).hexdigest()[:16]


def topic_id(name):
    return "TOP-" + hashlib.sha256(name.encode()).hexdigest()[:16]


async def seed():
    corpus = json.loads((ROOT / "data/corpus.json").read_text(encoding="utf-8"))
    async with Session.begin() as session:
        if await session.get(Project, "tpe"):
            return
        session.add(Project(id="tpe", name="TRON POOL ENERGY"))
        await session.flush()
        for s in corpus["sources"]:
            session.add(Source(
                id=s["id"], project_id="tpe", name=s["name"], url=s["url"],
                kind=s["type"], snapshot_hash=s["snapshotHash"],
                fetched_at=datetime.fromisoformat(s["fetchedAt"]),
            ))
        await session.flush()
        for d in corpus["documents"]:
            session.add(Document(
                id=d["id"], project_id="tpe", source_id=d["sourceId"], title=d["title"],
                language=d["language"], topic=d["topic"], status="Processed",
                live=d["live"], updated=date.fromisoformat(d["updated"]),
            ))
        await session.flush()
        for d in corpus["documents"]:
            raw = "\n\n".join(c["text"] for c in corpus["chunks"] if c["documentId"] == d["id"])
            session.add(DocumentVersion(
                id="VER-" + d["id"], document_id=d["id"], number=1, label=d["version"],
                raw_body=raw, body_hash=hashlib.sha256(raw.encode()).hexdigest(),
                status="Processed", change=d["history"][0]["change"],
                created_at=datetime.fromisoformat(d["updated"]).replace(tzinfo=timezone.utc),
            ))
        await session.flush()
        for d in corpus["documents"]:
            doc = await session.get(Document, d["id"])
            doc.current_version_id = "VER-" + d["id"]
            for i, section in enumerate(d["sections"]):
                session.add(Section(
                    id=section["id"], version_id=doc.current_version_id,
                    title=section["title"], position=i,
                ))
        await session.flush()
        docs = {d["id"]: d for d in corpus["documents"]}
        for i, c in enumerate(corpus["chunks"]):
            d = docs[c["documentId"]]
            session.add(Chunk(
                id=c["id"], document_id=d["id"], version_id="VER-" + d["id"],
                section_id=c["sectionId"], position=i, text=c["text"],
                language=d["language"], status=c["status"], embedding=c["embedding"],
                embedding_model=corpus["embeddingModel"], input_hash=c["inputHash"],
                verification_note=c.get("verificationNote", ""),
                checked_at=date.fromisoformat(d["updated"]) if c["status"] == "Verified" else None,
            ))
        names = {e for c in corpus["chunks"] for e in c["entities"]}
        names |= {e for a in corpus["facts"] + corpus["claims"] for e in a["entities"]}
        topics = {d["topic"] for d in corpus["documents"]}
        topics |= {a["topic"] for a in corpus["facts"] + corpus["claims"]}
        for name in names:
            session.add(Entity(id=entity_id(name), project_id="tpe", name=name))
        for name in topics:
            session.add(Topic(id=topic_id(name), project_id="tpe", name=name))
        await session.flush()
        for c in corpus["chunks"]:
            for name in c["entities"]:
                session.add(ChunkEntity(chunk_id=c["id"], entity_id=entity_id(name)))
        for kind, key in [("Fact", "facts"), ("Claim", "claims")]:
            for a in corpus[key]:
                session.add(Assertion(
                    id=a["id"], project_id="tpe", text=a["text"], kind=kind,
                    status=a["status"], topic_id=topic_id(a["topic"]),
                    checked_at=date.fromisoformat(a["checkedAt"]) if a.get("checkedAt") else None,
                    reason=a.get("reason", ""),
                ))
        await session.flush()
        chunks = {c["id"]: c for c in corpus["chunks"]}
        for a in corpus["facts"] + corpus["claims"]:
            for cid in a["chunkIds"]:
                sid = docs[chunks[cid]["documentId"]]["sourceId"]
                if sid not in a["sourceIds"]:
                    raise ValueError("Seed assertion source does not match its evidence.")
                session.add(AssertionEvidence(assertion_id=a["id"], chunk_id=cid, source_id=sid))
            for name in a["entities"]:
                session.add(AssertionEntity(assertion_id=a["id"], entity_id=entity_id(name)))
        for query, example in corpus["examples"].items():
            session.add(SavedExample(query=query, project_id="tpe", data=example))
