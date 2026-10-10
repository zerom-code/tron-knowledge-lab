import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings

origin = os.environ.get("PROTOTYPE_ORIGIN", "http://127.0.0.1:8000")
live = os.environ.get("RUN_LIVE_TESTS") == "1"
output = Path("artifacts/qa")
output.mkdir(parents=True, exist_ok=True)
checks, errors = [], []
token = settings.editor_token.get_secret_value()
if not token:
    raise SystemExit("Set EDITOR_TOKEN in .env before running editor checks.")


def check(name, condition):
    assert condition, name
    checks.append(name)
    print("PASS", name, flush=True)


def corpus(page):
    return page.request.get(origin + "/api/bootstrap").json()


with sync_playwright() as playwright:
    executable = os.environ.get("BROWSER_EXECUTABLE")
    if not executable and Path("/usr/bin/chromium").exists():
        executable = "/usr/bin/chromium"
    browser = playwright.chromium.launch(**({"executable_path": executable} if executable else {}), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.set_default_timeout(90000)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('kb-python-mode','saved')")
    page.goto(origin)
    page.get_by_role("heading", name="Knowledge Base", exact=True).wait_for()
    page.get_by_role("button", name="Добавить статью", exact=True).click()
    dialog = page.locator("#import-dialog")
    check("Import directly exposes password field and its .env location", dialog.locator("[data-editor-password]").is_visible() and "EDITOR_TOKEN" in dialog.inner_text())
    page.locator("#import-name").fill("Editor browser regression")
    page.locator("#import-url").fill("https://developers.tron.network/docs/bandwidth-and-energy")
    initial = corpus(page)
    selected = [c["text"] for c in initial["chunks"] if c["id"] in ["CHK-301", "CHK-304"]]
    page.locator("#import-body").fill("\n\n".join(selected))
    page.get_by_role("button", name="Начать обработку", exact=True).click()
    error = dialog.locator("[data-dialog-error]")
    error.wait_for(state="visible")
    check("Missing password error is inside the modal", "Введите пароль" in error.inner_text() and dialog.is_visible())
    check("Form values survive authentication failure", page.locator("#import-name").input_value() == "Editor browser regression")
    dialog.locator("[data-editor-password]").fill("incorrect-editor-fixture")
    dialog.get_by_role("button", name="Подключить редактора", exact=True).click()
    page.wait_for_function("document.querySelector('#import-dialog [data-dialog-error]').textContent.includes('Неверный пароль')")
    check("Wrong password keeps a visible actionable error", error.is_visible())
    page.screenshot(path=str(output / "09-import-error.png"))
    dialog.locator("[data-editor-password]").fill(token)
    dialog.locator("[data-editor-password]").press("Enter")
    page.wait_for_function("KB_LAB.getSnapshot().editorAuthenticated")
    check("Enter validates password without closing import", dialog.is_visible())
    check("Connected state removes credential from input", dialog.locator("[data-editor-password]").input_value() == "" and dialog.locator("[data-auth-connected]").is_visible())
    page.screenshot(path=str(output / "10-import-connected.png"))
    with page.expect_response(lambda r: r.url.endswith("/api/documents") and r.request.method == "POST") as pending:
        page.get_by_role("button", name="Начать обработку", exact=True).click()
    did = pending.value.json()["documentId"]
    page.wait_for_function("(did)=>KB_LAB.getSnapshot().documents.some(d=>d.id===did&&d.status==='Processed')", arg=did)
    doc = next(d for d in corpus(page)["documents"] if d["id"] == did)
    check("Contiguous paragraphs share one section", len(doc["sections"]) == 1 and len(doc["sections"][0]["chunks"]) == 2)
    check("Cached source embeddings finish without auto-verification", doc["embedded"] == 2 and all(c["status"] == "Unverified" for c in corpus(page)["chunks"] if c["documentId"] == did))
    for _ in range(2):
        page.get_by_role("button", name="Сверить с источником", exact=True).first.click()
        review = page.locator("#review-dialog")
        page.locator("#review-note").fill("Browser regression: сверено с сохранённой документацией TRON о Bandwidth и Energy.")
        page.locator("#review-checked").check()
        review.get_by_role("button", name="Сохранить проверку", exact=True).click()
        review.wait_for(state="hidden")
    check("Editor verification persists two evidence-linked facts", len([f for f in corpus(page)["facts"] if any(c["documentId"] == did and c["id"] in f["chunkIds"] for c in corpus(page)["chunks"])]) == 2)
    page.get_by_role("button", name="Найти в RAG", exact=False).click()
    page.get_by_role("button", name="Выполнить поиск", exact=True).click()
    page.wait_for_function("KB_LAB.getSnapshot().results!==null")
    result = page.evaluate("KB_LAB.getSnapshot().results")
    check("Saved mode never invents ratings for new chunk IDs", result["reranker"] == "не выполнен" and all(not c["scored"] for c in result["items"]))
    check("Saved mode offers explicit paid Live search action", page.get_by_role("button", name="Выполнить поиск через OpenAI", exact=True).is_visible())
    if live:
        page.locator("#rag-query").fill("Как ресурсы Energy и Bandwidth связаны со стоимостью транзакций TRON?")
        page.get_by_role("button", name="Выполнить поиск", exact=True).click()
        page.wait_for_function("KB_LAB.getSnapshot().results!==null")
        page.get_by_role("button", name="Выполнить поиск через OpenAI", exact=True).click()
        page.wait_for_function("KB_LAB.getSnapshot().results?.mode==='live' || KB_LAB.getSnapshot().error")
        state = page.evaluate("KB_LAB.getSnapshot()")
        check("Live action runs actual OpenAI and updates visible mode", not state["error"] and state["context"]["ok"] and page.locator("#search-mode").input_value() == "live")
        check("Live reranking covers only the imported source", all(c["documentId"] == did and c["scored"] for c in state["results"]["items"]))
        page.get_by_role("button", name="Посмотреть контекст", exact=False).click()
        page.get_by_role("button", name="Передать контекст AI", exact=True).click()
        page.wait_for_function("KB_LAB.getSnapshot().answer!==null || KB_LAB.getSnapshot().error")
        state = page.evaluate("KB_LAB.getSnapshot()")
        check("Imported source generates a citation-checked Live answer", not state["error"] and state["answer"]["evidenceReview"]["passed"])
        live_result = {"result": state["results"], "context": state["context"], "answer": state["answer"]}
        (output / "editor-live.json").write_text(json.dumps(live_result, ensure_ascii=False, indent=2), encoding="utf-8")
    page.goto(origin + "/#document/" + did)
    page.wait_for_function("KB_LAB.getSnapshot().editorAuthenticated")
    page.get_by_role("button", name="Исключить из поиска", exact=True).click()
    page.get_by_text("Документ исключён из поиска", exact=True).wait_for()
    check("Archiving the imported fixture persists in PostgreSQL", not next(d for d in corpus(page)["documents"] if d["id"] == did)["live"])
    page.get_by_role("button", name="Редактор", exact=True).click()
    api_dialog = page.locator("#api-dialog")
    api_dialog.get_by_role("button", name="Выйти", exact=True).click()
    check("Disconnect removes editor access", not page.evaluate("KB_LAB.getSnapshot().editorAuthenticated"))
    api_dialog.get_by_role("button", name="Закрыть", exact=True).click()
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Пароль редактора", exact=True).click()
    check("Password modal fits a mobile viewport", page.evaluate("document.documentElement.scrollWidth<=innerWidth") and api_dialog.is_visible())
    api_dialog.get_by_role("button", name="Закрыть", exact=True).click()
    page.get_by_role("link", name="Knowledge Base", exact=False).click()
    page.get_by_role("button", name="Добавить статью", exact=True).click()
    dialog.get_by_role("button", name="Закрыть", exact=True).click()
    check("Empty import can close without validation", not dialog.is_visible())
    check("Editor flow has no unhandled JavaScript errors", not errors)
    (output / "editor-report.json").write_text(json.dumps({"date": datetime.now(timezone.utc).isoformat(), "checks": len(checks), "passed": checks, "errors": errors, "live": live}, ensure_ascii=False, indent=2), encoding="utf-8")
    browser.close()
