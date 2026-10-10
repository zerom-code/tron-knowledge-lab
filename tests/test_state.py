import httpx
import pytest
from sqlalchemy import delete, select
from app.config import settings
from app.context import build
from app.db import Session
from app.errors import AppError
from app.main import app
from app.models import Document, RateBucket
from app.quotas import reserve
from app.rag import search
from app.schemas import SearchInput
from starlette.requests import Request

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_archiving_after_search_invalidates_old_context():
    async with Session() as session:
        result = await search(session, SearchInput(query="How can I reduce USDT TRC-20 transaction fees?"))
        target = await session.get(Document, "DOC-001")
        target.live = False
        await session.flush()
        try:
            selected = [c["id"] for c in result["items"] if c["documentId"] == "DOC-001"][:6]
            context = await build(session, result, selected)
            assert not context["chunks"] and not context["ok"]
            assert any("статус индекса" in e["reason"] for e in context["exclusions"])
        finally:
            await session.rollback()


async def test_atomic_quota_does_not_charge_global_bucket_on_denied_visitor(monkeypatch):
    import app.quotas as quotas
    class FakeDate:
        @classmethod
        def now(cls, tz):
            from datetime import datetime
            return datetime(2099, 1, 1, tzinfo=tz)
    monkeypatch.setattr(quotas, "datetime", FakeDate)
    monkeypatch.setattr(settings, "daily_visitor_limit", 1)
    monkeypatch.setattr(settings, "daily_global_limit", 10)
    request = Request({"type": "http", "method": "POST", "path": "/",
                       "headers": [], "client": ("quota-test", 1234)})
    async with Session.begin() as session:
        await session.execute(delete(RateBucket).where(RateBucket.bucket.startswith("2099-01-01:")))
    try:
        await reserve(request)
        with pytest.raises(AppError) as denied:
            await reserve(request)
        assert denied.value.status == 429
        async with Session() as session:
            global_bucket = await session.get(RateBucket, "2099-01-01:global")
            assert global_bucket.used == 1
    finally:
        async with Session.begin() as session:
            await session.execute(delete(RateBucket).where(RateBucket.bucket.startswith("2099-01-01:")))


async def test_extra_client_evidence_is_rejected_without_provider_calls():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        response = await client.post("/api/answer", json={
            "run_id": "anything", "selected_ids": [], "facts": [{"text": "Invented"}],
        })
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
