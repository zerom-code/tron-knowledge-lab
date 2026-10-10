import json
import os
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

origin = os.environ.get("PROTOTYPE_ORIGIN", "http://127.0.0.1:8000")
output = Path("artifacts/qa")
output.mkdir(parents=True, exist_ok=True)
checks, errors = [], []


def check(name, condition):
    assert condition, name
    checks.append(name)
    print("PASS", name)


def snapshot(page):
    return page.evaluate("KB_LAB.getSnapshot()")


def navigate(page, screen):
    page.locator('a[href="#' + screen + '"]').first.click()
    page.wait_for_function("(screen)=>KB_LAB.getSnapshot().screen===screen", arg=screen)


def search(page, example="Снижение комиссии"):
    navigate(page, "search")
    page.get_by_role("button", name=example, exact=True).click()
    page.get_by_role("button", name="Выполнить поиск", exact=True).click()
    page.wait_for_function("KB_LAB.getSnapshot().results!==null || KB_LAB.getSnapshot().error")
    assert not snapshot(page)["error"], snapshot(page)["error"]


with sync_playwright() as playwright:
    executable = os.environ.get("BROWSER_EXECUTABLE")
    if not executable and Path("/usr/bin/chromium").exists():
        executable = "/usr/bin/chromium"
    browser = playwright.chromium.launch(
        **({"executable_path": executable} if executable else {}), args=["--no-sandbox"])
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script("sessionStorage.setItem('kb-python-mode','saved')")
        page.goto(origin)
        page.get_by_role("heading", name="Knowledge Base", exact=True).wait_for()
        check("Persisted seed documents are loaded through Python", len(snapshot(page)["documents"]) >= 4)
        page.screenshot(path=str(output / "01-kb.png"), full_page=True)
        page.get_by_role("button", name="Начать сценарий", exact=True).click()
        check("Document decomposes into six exact source chunks", page.locator(".chunk-card").count() == 6)
        page.get_by_role("tab", name="Facts & Claims").click()
        check("Unverified marketing claim is separate from facts", page.get_by_text("CLAIM-01", exact=True).count() == 1)
        page.get_by_role("tab", name="Entities & Sources").click()
        check("Source opens the actual public article", page.locator(".source-card a").get_attribute("href") == "https://tronpoolenergy.com/how-it-works/")
        page.get_by_role("tab", name="Chunks", exact=True).click()
        page.screenshot(path=str(output / "02-document.png"), full_page=True)
        search(page)
        state = snapshot(page)
        check("Both PostgreSQL retrieval paths return candidates", state["results"]["vectorCount"] > 0 and state["results"]["ftsCount"] > 0)
        check("Context is bounded and verified", state["context"]["ok"] and len(state["context"]["chunks"]) <= 6 and all(c["status"] == "Verified" for c in state["context"]["chunks"]))
        check("UI labels actual PostgreSQL FTS instead of BM25", "PostgreSQL FTS" in page.locator("body").inner_text())
        page.screenshot(path=str(output / "03-search.png"), full_page=True)
        page.get_by_role("button", name="Посмотреть контекст", exact=False).click()
        with page.expect_download() as pending:
            page.get_by_role("button", name="Скачать JSON", exact=True).click()
        path = output / "context.json"
        pending.value.save_as(str(path))
        context = json.loads(path.read_text(encoding="utf-8"))
        check("Context JSON exports source URLs and evidence", bool(context["chunks"]) and all(s["url"].startswith("https://") for s in context["sources"]))
        page.screenshot(path=str(output / "04-context.png"), full_page=True)
        page.get_by_role("button", name="Передать контекст AI", exact=True).click()
        page.locator(".citation").first.wait_for()
        state = snapshot(page)
        check("Saved real OpenAI answer is explicitly labeled", state["answer"]["mode"] == "saved" and "сохранённый ответ" in page.locator("body").inner_text())
        check("Answer retains its source evidence review", state["answer"]["evidenceReview"]["passed"])
        page.screenshot(path=str(output / "05-answer.png"), full_page=True)
        cid = page.locator(".citation").first.get_attribute("data-chunk")
        page.locator(".citation").first.click()
        page.locator("#" + cid + ".selected").wait_for()
        check("Citation opens its exact chunk", page.locator("#" + cid + ".selected").count() == 1)
        search(page)
        while page.locator("[data-chunk-selection]:checked").count():
            cid = page.locator("[data-chunk-selection]:checked").first.get_attribute("data-chunk-selection")
            page.locator('[data-chunk-selection="' + cid + '"]').uncheck()
            page.wait_for_function("!KB_LAB.getSnapshot().context.reasons.includes('Контекст пересчитывается на сервере.')")
        check("Removing selected chunks triggers server Low Confidence", not snapshot(page)["context"]["ok"])
        page.get_by_role("button", name="Посмотреть контекст", exact=False).click()
        check("Low context blocks generation in UI", page.get_by_role("button", name="Передать контекст AI", exact=True).count() == 0)
        page.locator('a[data-action="example-refusal"]').click()
        page.wait_for_function("KB_LAB.getSnapshot().screen==='low' && KB_LAB.getSnapshot().results!==null")
        check("Future fee is refused with concrete reasons", snapshot(page)["results"]["info"]["future"] and not snapshot(page)["context"]["ok"])
        page.screenshot(path=str(output / "06-low.png"), full_page=True)
        search(page, "На русском")
        check("Russian question can retrieve English evidence", snapshot(page)["context"]["ok"])
        search(page)
        page.locator('[data-filter="source"]').select_option("TRON Docs")
        page.get_by_role("button", name="Выполнить поиск", exact=True).click()
        page.wait_for_function("KB_LAB.getSnapshot().results!==null")
        check("Source filter controls both retrieval paths", all(c["source"] == "TRON Docs" for c in snapshot(page)["results"]["items"]))
        search(page)
        page.locator('[data-filter="date"]').fill("2030-01-01")
        page.get_by_role("button", name="Выполнить поиск", exact=True).click()
        page.wait_for_function("KB_LAB.getSnapshot().results!==null")
        check("Future snapshot date produces empty context", not snapshot(page)["results"]["items"] and not snapshot(page)["context"]["ok"])
        navigate(page, "architecture")
        check("Architecture shows implemented FastAPI and pgvector", "Python / FastAPI" in page.locator("body").inner_text() and "PostgreSQL + pgvector" in page.locator("body").inner_text())
        page.screenshot(path=str(output / "07-architecture.png"), full_page=True)
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.add_init_script("sessionStorage.setItem('kb-python-mode','saved')")
        mobile.on("pageerror", lambda error: errors.append(str(error)))
        mobile.goto(origin)
        mobile.get_by_role("heading", name="Knowledge Base", exact=True).wait_for()
        for screen in ["kb", "document", "search", "context", "answer", "low", "architecture"]:
            if screen == "context":
                search(mobile)
                mobile.get_by_role("button", name="Посмотреть контекст", exact=False).click()
            elif screen == "answer":
                mobile.get_by_role("button", name="Передать контекст AI", exact=True).click()
                mobile.locator(".citation").first.wait_for()
            else:
                navigate(mobile, screen)
            check("Mobile " + screen + " fits viewport", mobile.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        mobile.screenshot(path=str(output / "08-mobile.png"), full_page=True)
        check("No unhandled browser errors", not errors)
        (output / "browser-report.json").write_text(json.dumps({
            "date": datetime.now(timezone.utc).isoformat(), "origin": origin,
            "checks": len(checks), "passed": checks, "errors": errors,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("TOTAL", len(checks), "passed")
    finally:
        browser.close()
