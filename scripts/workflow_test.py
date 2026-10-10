import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings

if os.environ.get("RUN_LIVE_TESTS") != "1":
    raise SystemExit("Set RUN_LIVE_TESTS=1 to allow real OpenAI charges.")

origin = os.environ.get("PROTOTYPE_ORIGIN", "http://127.0.0.1:8000")
headers = {"X-Editor-Token": settings.editor_token.get_secret_value()}
checks = []


def check(name, condition):
    assert condition, name
    checks.append(name)
    print("PASS", name)


def wait_doc(client, did):
    for _ in range(300):
        corpus = client.get(origin + "/api/bootstrap").json()
        doc = next(d for d in corpus["documents"] if d["id"] == did)
        if doc["status"] in ["Failed", "Processed"]:
            return doc, corpus
        time.sleep(.25)
    raise AssertionError("Processing did not finish in 75 seconds.")


with httpx.Client(trust_env=False, timeout=180) as client:
    corpus = client.get(origin + "/api/bootstrap").json()
    chunks = {c["id"]: c for c in corpus["chunks"]}
    source = next(s for s in corpus["sources"] if s["documentId"] == "DOC-003")
    # The second excerpt is an exact source prefix with a NEW embedding input.
    text = "\n\n".join([
        chunks["CHK-301"]["text"],
        " ".join(re.split(r"(?<=[.!?])\s+", chunks["CHK-304"]["text"])[:2]),
    ])
    payload = {"title": "QA fixture — real resource excerpts", "url": source["url"],
               "body": "", "language": "EN", "topic": "Resource model"}
    response = client.post(origin + "/api/documents", headers=headers, json=payload)
    check("New article is durably queued", response.status_code == 202)
    did = response.json()["documentId"]
    doc, _ = wait_doc(client, did)
    check("Missing body produces a persisted parsing failure", doc["status"] == "Failed" and doc["error"].startswith("PARSING_ERROR"))
    payload["body"] = text
    response = client.post(origin + "/api/documents/" + did + "/retry", headers=headers, json=payload)
    check("Retry keeps the document identity", response.status_code == 202 and response.json()["documentId"] == did)
    doc, corpus = wait_doc(client, did)
    check("Python pipeline finishes with actual embeddings", doc["status"] == "Processed" and doc["embedded"] == 2)
    check("Both attempts remain in version history", len(doc["history"]) == 2)
    new_chunks = [c for c in corpus["chunks"] if c["documentId"] == did]
    check("Processed does not auto-verify new knowledge", all(c["status"] == "Unverified" for c in new_chunks))
    check("Reload reads the persisted document", any(d["id"] == did for d in client.get(origin + "/api/bootstrap").json()["documents"]))
    for chunk in new_chunks:
        response = client.post(origin + "/api/chunks/" + chunk["id"] + "/verify", headers=headers, json={
            "note": "QA: точная выдержка сверена с ранее сохранённой документацией TRON.",
            "checked_against_source": True,
        })
        assert response.status_code == 200, response.text
    corpus = client.get(origin + "/api/bootstrap").json()
    check("Source review persists facts with evidence links", len([
        f for f in corpus["facts"] if set(f["chunkIds"]) & {c["id"] for c in new_chunks}
    ]) == 2)
    response = client.post(origin + "/api/search", json={
        "query": "Как ресурсы Energy и Bandwidth связаны со стоимостью транзакций TRON?",
        "filters": {"document": did, "verification": "Verified"}, "mode": "live",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    check("New document participates in BOTH database search paths", result["vectorCount"] > 0 and result["ftsCount"] > 0 and all(c["documentId"] == did for c in result["items"]))
    check("Its reviewed evidence builds sufficient bounded context", result["context"]["ok"])
    response = client.post(origin + "/api/answer", json={
        "run_id": result["runId"], "selected_ids": result["selected_ids"],
    })
    assert response.status_code == 200, response.text
    answer = response.json()
    check("New answer passes paragraph evidence review", answer["answerable"] and answer["mode"] == "live" and answer["evidenceReview"]["passed"])
    check("Answer cites only the newly imported source chunks", all(
        set(p["chunk_ids"]) <= {c["id"] for c in new_chunks} for p in answer["paragraphs"]))
    response = client.post(origin + "/api/documents/" + did + "/live", headers=headers, json={"live": False})
    assert response.status_code == 200
    excluded = client.post(origin + "/api/search", json={
        "query": corpus["defaultQuery"], "filters": {"document": did},
    }).json()
    check("Excluding document removes it from both retrieval paths", excluded["candidateCount"] == 0 and not excluded["items"])
    Path("artifacts/qa").mkdir(parents=True, exist_ok=True)
    Path("artifacts/qa/workflow-report.json").write_text(json.dumps({
        "date": datetime.now(timezone.utc).isoformat(), "checks": len(checks),
        "passed": checks, "documentId": did, "answer": answer,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TOTAL", len(checks), "passed; test document archived for inspection:", did)
