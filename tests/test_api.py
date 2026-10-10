import httpx
import pytest
from app.main import app
from app.config import settings
from pydantic import SecretStr

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_same_origin_foreign_project_and_editor_access(monkeypatch):
    monkeypatch.setattr(settings, "editor_token", SecretStr("test-editor-fixture"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        assert (await client.get("/api/health")).json()["backend"] == "Python / FastAPI"
        denied = await client.post("/api/search", json={"query": "TRON Energy"}, headers={"Origin": "https://evil.example"})
        assert denied.status_code == 403
        foreign = await client.post("/api/search", json={"query": "TRON Energy", "project_id": "another"})
        assert foreign.status_code == 422
        editor = await client.post("/api/documents", json={"title": "test", "body": "", "url": "https://example.org/"})
        assert editor.status_code == 403


async def test_private_files_and_oversized_requests_are_not_served():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        for path in ["/.env", "/.dev.vars", "/app/config.py", "/data/corpus.json"]:
            assert (await client.get(path)).status_code == 404
        too_large = await client.post("/api/search", content="x" * 25000)
        assert too_large.status_code == 413


async def test_context_and_answer_reject_unknown_run_without_openai():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        for path in ["/api/context", "/api/answer"]:
            response = await client.post(path, json={"run_id": "forged", "selected_ids": ["CHK-101"]})
            assert response.status_code == 404 and response.json()["error"]["code"] == "UNKNOWN_RUN"


@pytest.mark.parametrize("configured", ["", "replace_with_a_private_editor_password"])
async def test_editor_placeholder_cannot_unlock_changes(monkeypatch, configured):
    monkeypatch.setattr(settings, "editor_token", SecretStr(configured))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        response = await client.post("/api/editor/check", headers={"X-Editor-Token": configured})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "EDITOR_NOT_CONFIGURED"


async def test_editor_check_validates_without_exposing_password(monkeypatch):
    token = "private-test-editor-fixture"
    monkeypatch.setattr(settings, "editor_token", SecretStr(token))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client:
        denied = await client.post("/api/editor/check", headers={"X-Editor-Token": "incorrect"})
        assert denied.status_code == 403
        assert token not in denied.text
        allowed = await client.post("/api/editor/check", headers={"X-Editor-Token": token})
        assert allowed.status_code == 200 and allowed.json() == {"authenticated": True}
        health = await client.get("/api/health")
        assert health.json()["editorConfigured"] and token not in health.text
