import pytest
from sqlalchemy import text
from app.context import build, choose
from app.db import Session
from app.models import SavedExample, SearchRun
from app.rag import search
from app.repository import snapshot
from app.schemas import SearchInput
from app.agent import answer
from app.errors import AppError

pytestmark = pytest.mark.asyncio(loop_scope="session")
QUESTION = "How can I reduce USDT TRC-20 transaction fees?"


async def test_actual_postgresql_and_pgvector_are_used():
    async with Session() as session:
        assert await session.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        corpus = await snapshot(session)
        assert {d["id"] for d in corpus["documents"]} >= {"DOC-001", "DOC-002", "DOC-003", "DOC-004"}
        assert len(corpus["facts"]) >= 8
        assert all("embedding" not in c for c in corpus["chunks"])


async def test_hybrid_uses_both_sql_paths_and_persists_run():
    async with Session() as session:
        result = await search(session, SearchInput(query=QUESTION))
        assert result["vectorCount"] > 0 and result["ftsCount"] > 0
        assert await session.get(SearchRun, result["runId"])
        assert "PostgreSQL FTS" in result["lexicalMethod"]


@pytest.mark.parametrize("filters", [
    {"language": "RU"}, {"date": "2030-01-01"},
    {"document": "missing"}, {"entity": "missing"},
])
async def test_empty_prefilters_affect_both_search_paths(filters):
    async with Session() as session:
        result = await search(session, SearchInput(query=QUESTION, filters=filters))
        assert result["vectorCount"] == result["ftsCount"] == result["candidateCount"] == 0
        assert not (await build(session, result, []))["ok"]


async def test_source_and_verification_filters_are_applied_before_fusion():
    async with Session() as session:
        result = await search(session, SearchInput(query=QUESTION, filters={
            "source": "TRON Docs", "verification": "Verified",
        }))
        assert result["items"]
        assert all(c["source"] == "TRON Docs" and c["status"] == "Verified" for c in result["items"])


async def test_context_limits_evidence_sources_and_unverified_exclusion():
    async with Session() as session:
        result = await search(session, SearchInput(query=QUESTION))
        corpus = await snapshot(session)
        context = await build(session, result, choose(corpus, result))
        assert context["ok"] and len(context["chunks"]) <= 6 and context["textChars"] <= 7800
        ids = {c["id"] for c in context["chunks"]}
        assert all(c["status"] == "Verified" for c in context["chunks"])
        docs = {d["id"]: d for d in corpus["documents"]}
        chunks = {c["id"]: c for c in corpus["chunks"]}
        for fact in context["facts"]:
            assert set(fact["chunkIds"]) <= ids
            actual_sources = {docs[chunks[cid]["documentId"]]["sourceId"] for cid in fact["chunkIds"]}
            assert set(fact["sourceIds"]) <= actual_sources
        assert not (await build(session, result, []))["ok"]
        with pytest.raises(AppError):
            await build(session, result, ["forged"])


async def test_saved_answer_has_real_provenance_and_future_quote_is_refused():
    async with Session() as session:
        result = await search(session, SearchInput(query=QUESTION))
        example = await session.get(SavedExample, QUESTION)
        context = await build(session, result, example.data["selection"])
        output = await answer(session, result, context)
        assert output["answerable"] and output["evidenceReview"]["passed"] and output["mode"] == "saved"
        assert "gpt-4.1-mini" in output["model"]
        refused = await search(session, SearchInput(query="What exact fee will I pay tomorrow for USDT TRC-20?"))
        assert not (await answer(session, refused, await build(session, refused, [])))["answerable"]
