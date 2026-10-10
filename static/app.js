const LIMITS = window.KB_HEALTH.limits;
(() => {
  "use strict";
  const preference = (key, fallback = "") => {
    try {
      return sessionStorage.getItem(key) ?? fallback;
    } catch {
      return fallback;
    }
  };
  let db = window.KB_DATA;
  const names = {
    kb: "Knowledge Base",
    document: "Document",
    search: "RAG Search",
    context: "Retrieved Context",
    answer: "AI Answer",
    low: "Low Confidence",
    architecture: "Архитектура",
  };
  const stageNames = [
    "Article",
    "Parsing",
    "Sections",
    "Chunks",
    "Facts / Claims",
    "Embeddings",
    "Knowledge Base",
  ];
  const state = {
    screen: "kb",
    documentId: "DOC-001",
    chunkId: "CHK-101",
    docTab: "structure",
    query: db.defaultQuery,
    filters: {
      language: "EN",
      source: "",
      topic: "",
      entity: "",
      document: "",
      date: "",
      verification: "",
    },
    results: null,
    selected: new Set(),
    searching: false,
    generating: false,
    answerReady: false,
    kbQuery: "",
    kbStatus: "",
    answer: null,
    error: "",
    mode: preference("kb-python-mode", window.KB_HEALTH.defaultMode),
    editorToken: preference("kb-python-editor"),
    editorAuthenticated: false,
    importBusy: false,
    context: null,
    contextBusy: false,
  };
  const icons = {
    layers: '<path d="m3 7 9-5 9 5-9 5zM3 12l9 5 9-5M3 17l9 5 9-5"/>',
    database:
      '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    document: '<path d="M14 3H5v18h14V8zM14 3v6h5M8 13h8M8 17h5"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    context:
      '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h5M8 15h8M8 18h4"/>',
    spark:
      '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
    shield: '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6zM8 12l3 3 5-6"/>',
    warning: '<path d="m12 3 10 18H2zM12 9v5M12 17h.01"/>',
    architecture:
      '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-5h14v5"/>',
    arrow: '<path d="M4 12h16M14 6l6 6-6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    refresh:
      '<path d="M20 7v5h-5M4 17v-5h5M20 12a8 8 0 0 0-14-5M4 12a8 8 0 0 0 14 5"/>',
    link: '<path d="m9 15 6-6M8 17l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 7l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M4 16v5h16v-5"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 10v7M12 6h.01"/>',
    external: '<path d="M14 3h7v7M21 3l-9 9M10 3H3v18h18v-7"/>',
    filter: '<path d="M3 5h18l-7 8v7l-4-2v-5z"/>',
    key: '<circle cx="7" cy="8" r="4"/><path d="m10 11 10 10M15 16l3-3M18 19l3-3"/>',
  };
  const esc = (v) =>
    String(v ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const icon = (name, extra = "") =>
    `<svg class="icon ${extra}" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.document}</svg>`;
  const docById = (id) => db.documents.find((d) => d.id === id);
  const chunkById = (id) => db.chunks.find((c) => c.id === id);
  const chunksFor = (d) => db.chunks.filter((c) => c.documentId === d.id);
  const sourceById = (id) => db.sources.find((s) => s.id === id);
  const liveDocs = () =>
    db.documents.filter(
      (d) => d.searchable && d.embedded > 0 && d.projectId === db.projectId,
    );
  const formatDate = (value) =>
    value
      ? new Date(value + "T00:00:00Z").toLocaleDateString("ru-RU", {
          timeZone: "UTC",
          day: "2-digit",
          month: "short",
          year: "numeric",
        })
      : "—";
  function tag(label) {
    const styles = {
      Verified: "success",
      Processed: "success",
      Unverified: "warning",
      Queued: "warning",
      Outdated: "warning",
      Failed: "error",
      Processing: "processing",
      "No source": "error",
    };
    const title = ["Verified", "Unverified", "Outdated"].includes(label)
      ? "Verified: выдержка или факт сверены с сохранённым первоисточником. Unverified: для подтверждения недостаточно данных."
      : "";
    return `<span class="tag ${styles[label] || ""}" title="${title}"><span class="dot"></span>${esc(label)}</span>`;
  }
  const button = (label, action, style = "secondary", attrs = "") =>
    `<button class="button ${style}" data-action="${action}" ${attrs}>${label}</button>`;
  const docLink = (id, label, chunkId = "") =>
    `<button class="text-button" data-action="open-document" data-document="${esc(id)}" data-chunk="${esc(chunkId)}">${esc(label)}</button>`;
  function toast(message) {
    const dialog = document.querySelector("dialog[open]");
    if (dialog) {
      const status = dialog.querySelector("[data-dialog-status]");
      status.textContent = message;
      status.hidden = false;
      return;
    }
    const el = document.getElementById("toast");
    el.textContent = message;
    el.classList.add("visible");
    clearTimeout(toast.timeout);
    toast.timeout = setTimeout(() => el.classList.remove("visible"), 3200);
  }
  function shortId(id) {
    const match = id.match(/-(CHK|SEC)-(\d+)(?:-CLAIM)?$/);
    return match
      ? (match[1] === "CHK" ? "Chunk " : "Section ") + (Number(match[2]) + 1)
      : id;
  }
  function showError(error, dialog = document.querySelector("dialog[open]")) {
    if (["EDITOR_REQUIRED", "EDITOR_NOT_CONFIGURED"].includes(error.code)) {
      state.editorAuthenticated = false;
      state.editorToken = "";
      try {
        sessionStorage.removeItem("kb-python-editor");
      } catch {}
      render();
    }
    const message =
      error.name === "AbortError"
        ? "Время ожидания истекло. Повторите запрос."
        : error.message;
    if (dialog) {
      const box = dialog.querySelector("[data-dialog-error]");
      box.textContent = message;
      box.hidden = false;
      box.scrollIntoView({ block: "nearest" });
      if (error.code === "EDITOR_REQUIRED")
        dialog.querySelector("[data-editor-password]")?.focus();
    } else {
      state.error = message;
      render();
    }
  }
  function openDialog(id) {
    const dialog = document.getElementById(id);
    dialog
      .querySelectorAll("[data-dialog-error],[data-dialog-status]")
      .forEach((box) => {
        box.hidden = true;
        box.textContent = "";
      });
    renderEditorAccess();
    dialog.showModal();
    if (!state.editorAuthenticated)
      dialog.querySelector("[data-editor-password]")?.focus();
  }
  function renderEditorAccess() {
    for (const host of document.querySelectorAll("[data-editor-access]")) {
      if (!host.childElementCount) {
        host.className = "editor-access";
        host.innerHTML =
          '<div data-auth-fields><label class="field">Пароль редактора<input type="password" data-editor-password autocomplete="off" placeholder="Значение EDITOR_TOKEN из .env"></label><p class="field-hint">Пароль находится в строке EDITOR_TOKEN файла .env в папке проекта.</p><button type="button" class="button secondary" data-action="connect-editor">Подключить редактора</button></div><div data-auth-connected class="editor-connected"><span>Редактор подключён</span><button type="button" class="text-button" data-action="disconnect-editor">Выйти</button></div>';
      }
      host.querySelector("[data-auth-fields]").hidden =
        state.editorAuthenticated;
      host.querySelector("[data-auth-connected]").hidden =
        !state.editorAuthenticated;
    }
  }
  async function authenticateEditor(token) {
    if (!token) {
      const error = new Error("Введите пароль в поле «Пароль редактора».");
      error.code = "EDITOR_REQUIRED";
      throw error;
    }
    const response = await fetch("/api/editor/check", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Editor-Token": token },
      body: "{}",
      signal: AbortSignal.timeout(15000),
    });
    const data = await response.json();
    if (!response.ok) {
      state.editorAuthenticated = false;
      renderEditorAccess();
      const error = new Error(
        data.error?.message || "Не удалось проверить пароль.",
      );
      error.code = data.error?.code;
      throw error;
    }
    state.editorToken = token;
    state.editorAuthenticated = true;
    try {
      sessionStorage.setItem("kb-python-editor", token);
    } catch {}
    document.querySelectorAll("[data-editor-password]").forEach((input) => {
      input.value = "";
    });
    render();
  }
  async function requireEditor(dialog) {
    if (!state.editorAuthenticated)
      await authenticateEditor(
        dialog.querySelector("[data-editor-password]").value.trim(),
      );
  }
  function setMode(mode) {
    if (mode === "live" && !window.KB_HEALTH.liveAvailable)
      throw new Error(
        "Добавьте OPENAI_API_KEY в .env и перезапустите приложение.",
      );
    if (state.mode !== mode) {
      invalidateSearch();
      state.mode = mode;
    }
    try {
      sessionStorage.setItem("kb-python-mode", mode);
    } catch {}
  }
  function navigate(screen, documentId, chunkId) {
    const hash =
      screen === "document"
        ? `#document/${documentId || state.documentId}${chunkId ? "/" + chunkId : ""}`
        : "#" + screen;
    if (location.hash === hash) {
      route();
      return;
    }
    location.hash = hash;
  }
  function route() {
    const [screen, documentId, chunkId] = decodeURIComponent(
      location.hash.replace(/^#/, ""),
    ).split("/");
    state.screen = names[screen] ? screen : "kb";
    if (documentId && docById(documentId)) {
      state.documentId = documentId;
      state.docTab = "structure";
      state.chunkId = chunkId || chunksFor(docById(documentId))[0]?.id || "";
    }
    render();
    window.scrollTo({ top: 0, behavior: "instant" });
    document.querySelector("h1")?.focus({ preventScroll: true });
    if (chunkId)
      setTimeout(
        () =>
          document
            .getElementById(chunkId)
            ?.scrollIntoView({ block: "center", behavior: "smooth" }),
        70,
      );
  }
  function pageHead(kicker, title, description, actions = "") {
    return `<div class="page-head"><div><span class="eyebrow">${kicker}</span><h1 tabindex="-1">${title}</h1><p>${description}</p></div>${actions ? `<div class="head-actions">${actions}</div>` : ""}</div>`;
  }
  function journey() {
    const items = [
      ["kb", "Знания"],
      ["document", "Документ"],
      ["search", "Поиск"],
      ["context", "Контекст"],
      ["answer", "Ответ"],
    ];
    return `<nav class="journey" aria-label="Основной сценарий">${items.map(([id, label], i) => `${i ? '<span class="journey-separator"></span>' : ""}<a href="#${id}" class="${state.screen === id ? "current" : ""}" ${state.screen === id ? 'aria-current="step"' : ""}><span class="journey-number">0${i + 1}</span>${label}</a>`).join("")}</nav>`;
  }
  function render() {
    const navItems = [
      ["kb", "database", "Knowledge Base", "01"],
      ["document", "document", "Document", "02"],
      ["search", "search", "RAG Search", "03"],
      ["context", "context", "Retrieved Context", "04"],
      ["answer", "spark", "AI Answer", "05"],
    ];
    const screens = {
      kb: renderKB,
      document: renderDocument,
      search: renderSearch,
      context: renderContext,
      answer: renderAnswer,
      low: renderLow,
      architecture: renderArchitecture,
    };
    document.getElementById("app").innerHTML = `
      <aside class="sidebar"><div class="brand"><div class="brand-mark">${icon("layers")}</div><div class="brand-text"><div class="brand-title">Knowledge Lab</div><div class="brand-sub">TRON POOL ENERGY</div></div></div>
      <nav aria-label="Разделы прототипа"><div class="sidebar-label">KNOWLEDGE WORKSPACE</div>${navItems.map(([id, ic, label, count]) => `<a href="#${id}" class="nav-link ${state.screen === id ? "active" : ""}" title="${label}" ${state.screen === id ? 'aria-current="page"' : ""}>${icon(ic)}<span>${label}</span><span class="nav-count">${count}</span></a>`).join("")}
      <div class="sidebar-label">SYSTEM & EXPLORATION</div><a href="#low" data-action="example-refusal" class="nav-link ${state.screen === "low" ? "active" : ""}" title="Low Confidence">${icon("warning")}<span>Low Confidence</span></a><a href="#architecture" class="nav-link ${state.screen === "architecture" ? "active" : ""}" title="Архитектура">${icon("architecture")}<span>Архитектура</span></a></nav>
      </aside>
      <div class="workspace"><header class="topbar"><div class="breadcrumb"><span>${names[state.screen]}</span></div><div class="topbar-actions"><label class="mode-control">Режим поиска<select id="search-mode" aria-label="Режим поиска"><option value="saved" ${state.mode === "saved" ? "selected" : ""}>Сохранённые примеры</option><option value="live" ${state.mode === "live" ? "selected" : ""}>Live OpenAI</option></select></label>${button(icon(state.editorAuthenticated ? "check" : "key") + (state.editorAuthenticated ? "Редактор" : "Пароль редактора"), "open-api", "secondary")}${button(icon("refresh") + "Сбросить вид", "reset", "ghost")}</div></header>
      <main id="main" class="main" tabindex="-1"><div class="screen-enter">${state.error ? `<div class="alert error" role="alert">${icon("warning")}<p>${esc(state.error)}</p></div>` : ""}${screens[state.screen]()} </div></main></div>`;
    renderEditorAccess();
  }
  function renderKB() {
    const indexed = liveDocs(),
      indexedChunks = indexed.reduce((n, d) => n + chunksFor(d).length, 0);
    return (
      pageHead(
        "01 · База знаний",
        "Knowledge Base",
        "Документы, источники и версии.",
        button(icon("search") + "RAG Search", "go-search", "secondary") +
          button(icon("plus") + "Добавить статью", "open-import", "primary"),
      ) +
      journey() +
      `
      <div class="stats"><div class="stat"><div class="stat-label">Документы${icon("document")}</div><div class="stat-number">${db.documents.length}</div><small>${indexed.length} live-документов в индексе</small></div><div class="stat"><div class="stat-label">Chunks в индексе${icon("layers")}</div><div class="stat-number">${indexedChunks}</div></div><div class="stat"><div class="stat-label">Проверенные факты${icon("shield")}</div><div class="stat-number">${db.facts.filter((f) => f.status === "Verified").length}</div></div><div class="stat"><div class="stat-label">Embeddings${icon("check")}</div><div class="stat-number">${indexed.reduce((n, d) => n + d.embedded, 0)}<span style="font-size:16px;color:#8ba276"> / ${indexedChunks}</span></div></div></div>
      <section class="panel" aria-labelledby="documents-title"><div class="panel-head"><div><h2 id="documents-title">Документы проекта <span class="tag" style="margin-left:7px">${db.documents.length}</span></h2><p>Article → Section → Chunk</p></div><span class="tag">Сайт + TRON Docs</span></div><div class="table-tools"><div class="search-field">${icon("search")}<input id="kb-query" aria-label="Поиск документов по названию" placeholder="Найти документ…" value="${esc(state.kbQuery)}"></div><select id="kb-status" aria-label="Фильтр по статусу"><option value="">Все статусы</option>${["Processed", "Queued", "Processing", "Failed"].map((s) => `<option ${s === state.kbStatus ? "selected" : ""}>${s}</option>`).join("")}</select></div><div class="table-scroll"><table><thead><tr><th>Документ</th><th>Источник</th><th>Язык</th><th>Обработка</th><th>Получено</th><th>Chunks</th><th>Embeddings</th><th>Версия</th><th></th></tr></thead><tbody id="kb-rows">${kbRows()}</tbody></table></div><div class="table-foot"><span id="kb-row-count">${filteredDocs().length} из ${db.documents.length} документов</span><span>Только live + Processed + embeddings доступны RAG</span></div></section>
      <div class="bottom-grid"><section class="panel"><div class="panel-head"><div><h2>Источники знаний</h2><p>Сайт и документация TRON. Остальные интеграции запланированы.</p></div></div><div class="panel-body"><div class="connector-list"><span class="connector enabled"><span class="dot"></span>Сайт</span><span class="connector enabled"><span class="dot"></span>TRON Docs</span>${["GSC", "GA4", "Ahrefs", "AI Visibility"].map((x) => `<span class="connector">${x}<small>Planned</small></span>`).join("")}</div></div></section><section class="hint-card"><span class="eyebrow">Основной сценарий</span><h3 style="margin-top:8px">Статья → контекст → ответ</h3>${button("Начать сценарий " + icon("arrow"), "start-tour", "secondary")}</section></div>`
    );
  }
  function filteredDocs() {
    return db.documents.filter(
      (d) =>
        (!state.kbQuery ||
          (d.title + " " + d.id + " " + d.source)
            .toLowerCase()
            .includes(state.kbQuery.toLowerCase())) &&
        (!state.kbStatus || d.status === state.kbStatus),
    );
  }
  function kbRows() {
    const docs = filteredDocs();
    return docs.length
      ? docs
          .map(
            (d) =>
              `<tr><td><div class="doc-name"><div class="doc-icon">${icon("document", "small")}</div><div><strong>${docLink(d.id, d.title)}</strong><div class="mono">${d.id}${!d.live ? " · ARCHIVED / NOT INDEXED" : ""}</div></div></div></td><td>${esc(d.source)}</td><td><span class="tag">${d.language}</span></td><td>${tag(d.status)}</td><td>${formatDate(d.updated)}</td><td>${chunksFor(d).length}</td><td><span class="emb-count">${d.embedded ? icon("check", "small") : ""}${d.embedded || "—"}</span></td><td><span class="mono">v${d.version}</span></td><td><button class="icon-button" data-action="open-document" data-document="${d.id}" aria-label="Открыть ${esc(d.title)}">›</button></td></tr>`,
          )
          .join("")
      : '<tr><td colspan="9" style="text-align:center;padding:35px;color:var(--muted)">Документы не найдены. Измените название или статус.</td></tr>';
  }
  function renderDocument() {
    const d = docById(state.documentId) || db.documents[0],
      chunks = chunksFor(d),
      factCount = db.facts.filter((f) =>
        f.chunkIds.some((id) => chunks.some((c) => c.id === id)),
      ).length;
    return (
      pageHead(
        "02 · Документ",
        esc(d.title),
        "Разделы, фрагменты и связанные утверждения.",
        button("← К документам", "go-kb") +
          button(
            icon("search") + "Найти в RAG",
            "search-document",
            "primary",
            `data-document="${d.id}"`,
          ) +
          button(
            d.live ? "Исключить из поиска" : "Вернуть в поиск",
            "toggle-live",
            "secondary",
            `data-document="${d.id}"`,
          ),
      ) +
      journey() +
      `
      ${!d.live ? `<div class="alert info">${icon("info")}<div><strong>Документ исключён из поиска</strong><p>Снимок и его выдержки сохранены. Документ не участвует в поиске RAG.</p></div></div>` : ""}
      ${d.error ? `<div class="alert error">${icon("warning")}<div><strong>Обработка остановлена на этапе ${stageNames[d.failedStage || 1]}</strong><p class="mono">${esc(d.error)}</p><p>Снимок источника сохранён. Повторная обработка использует тот же документ и не создаёт дубликат.</p>${button("Повторить обработку", "retry-document", "secondary", `data-document="${d.id}"`)}</div></div>` : ""}
      <section class="panel"><div class="panel-body"><div class="metadata-grid"><div class="metadata-item"><small>Источник</small><strong>${esc(d.source)}</strong></div><div class="metadata-item"><small>Язык</small><strong>${d.language}</strong></div><div class="metadata-item"><small>Обработка</small>${tag(d.status)}</div><div class="metadata-item"><small>Версия</small><strong class="mono">v${d.version}${d.live ? " · live" : " · archived"}</strong></div><div class="metadata-item"><small>Получено</small><strong>${formatDate(d.updated)}</strong></div><div class="metadata-item"><small>Chunks / embeddings</small><strong>${chunks.length} / ${d.embedded}</strong></div><div class="metadata-item"><small>Модель embedding</small><strong class="mono">text-embedding-3-small</strong></div><div class="metadata-item"><small>Размерность · конфигурация</small><strong class="mono">${db.embeddingDimensions}</strong></div></div></div></section>
      <section class="panel"><div class="panel-head"><div><h2>Пайплайн обработки</h2><p>Processed — обработан. Verified — сверен с источником.</p></div>${tag(d.status)}</div>${processingPipeline(d)}<div class="panel-body" style="padding-top:0;font-size:10px;color:var(--muted)">${d.status === "Processing" ? "Обработка снимка статьи выполняется…" : d.status === "Failed" ? "Ошибка сохранена. Предыдущая успешная версия, если она есть, остаётся в поиске." : d.status === "Queued" ? "Документ в очереди Python worker. Новая версия ещё не участвует в поиске." : ""}</div></section>
      <div class="document-layout"><aside class="panel document-tree"><div class="tree-head"><h3>${icon("layers", "small")} Структура документа</h3></div><div class="tree">${d.sections.length ? d.sections.map((s) => `<details open><summary>${esc(s.title)}</summary>${s.chunks.map((id, i) => `<button class="tree-item ${state.chunkId === id ? "active" : ""}" data-action="select-chunk" data-chunk="${id}">${icon("document", "small")}<span>${esc(shortId(id))}</span></button>`).join("")}</details>`).join("") : '<div style="padding:15px;font-size:11px;color:var(--muted)">Разделы появятся после успешного parsing.</div>'}</div><div class="tree-foot">${d.sections.length} sections · ${chunks.length} chunks<br>${factCount} связанных фактов · ${d.entities.length} entities</div></aside>
      <section class="panel"><div class="tabs" role="tablist" aria-label="Информация о документе">${[
        ["structure", "Chunks"],
        ["knowledge", "Facts & Claims"],
        ["sources", "Entities & Sources"],
        ["history", "Версии"],
      ]
        .map(
          ([id, label]) =>
            `<button class="tab ${state.docTab === id ? "active" : ""}" role="tab" aria-selected="${state.docTab === id}" data-action="document-tab" data-tab="${id}">${label}</button>`,
        )
        .join(
          "",
        )}</div><div role="tabpanel">${documentTab(d, chunks)}</div></section></div>`
    );
  }
  function processingPipeline(d) {
    const job = d.job;
    let current =
      job?.stage ??
      (d.status === "Processed"
        ? 7
        : d.status === "Failed"
          ? d.failedStage || 1
          : 0);
    return `<div class="pipeline">${stageNames.map((name, i) => `${i ? '<span class="pipeline-arrow">→</span>' : ""}<div class="pipeline-node ${d.status === "Failed" && i === current ? "error" : i < current ? "done" : i === current && d.status === "Processing" ? "running" : ""}"><strong>${i < current ? "✓ " : ""}${name}</strong><small>${d.status === "Failed" && i === current ? "Failed" : i < current ? "Completed" : i === current && d.status === "Processing" ? "Processing" : "Pending"}</small></div>`).join("")}</div>`;
  }
  function documentTab(d, chunks) {
    if (state.docTab === "structure")
      return chunks.length
        ? chunks
            .map(
              (c) =>
                `<article id="${c.id}" class="chunk-card ${state.chunkId === c.id ? "selected" : ""}"><div class="chunk-top"><span class="mono">${esc(shortId(c.id))} <span style="color:#a0ac94">/</span> ${esc(d.sections.find((s) => s.id === c.sectionId)?.title || "Section")}</span>${tag(c.status)}</div><p>${esc(c.text)}</p><div class="chunk-bottom">${c.entities.map((e) => `<span class="entity">${esc(e)}</span>`).join("")}<span>·</span><span>v${d.version} · ${d.language} · ${esc(shortId(c.sectionId))}</span></div>${c.status === "Unverified" ? button("Сверить с источником", "review-chunk", "secondary", 'data-chunk="' + esc(c.id) + '"') : ""}</article>`,
            )
            .join("")
        : `<div class="empty"><div class="empty-icon">${icon("document")}</div><h2>Структура ещё не создана</h2><p>После обработки здесь появятся разделы, chunks и связи с извлечёнными знаниями.</p></div>`;
    if (state.docTab === "knowledge") {
      const facts = db.facts.filter((f) =>
          f.chunkIds.some((id) => chunks.some((c) => c.id === id)),
        ),
        claims = db.claims.filter((f) =>
          f.chunkIds.some((id) => chunks.some((c) => c.id === id)),
        );
      return `<div class="panel-body"><div class="inline-note" style="margin-top:0">${icon("info", "small")}<span>Fact — сверенное утверждение. Claim — непроверенное. Проверка относится к снимку источника.</span></div><h3 class="section-title">FACTS · ${facts.length}</h3>${facts.map((f) => relationCard(f, chunks)).join("") || '<p class="muted" style="font-size:12px">Проверенных фактов пока нет.</p>'}<h3 class="section-title" style="margin-top:20px">CLAIMS · ${claims.length}</h3>${claims.map((c) => relationCard(c, chunks)).join("") || '<p class="muted" style="font-size:12px">Отдельные неподтверждённые claims не извлечены.</p>'}</div>`;
    }
    if (state.docTab === "sources")
      return `<div class="panel-body"><h3 class="section-title">ENTITIES → TOPICS</h3><div class="relation-card"><div class="connector-list">${d.entities.map((e) => `<span class="tag">${esc(e)}</span>`).join("")}</div><p>Связаны с темой <strong>${esc(d.topic)}</strong> и конкретными chunks выше.</p></div><h3 class="section-title">SOURCE & PROVENANCE</h3>${d.sourceId ? sourceCard(sourceById(d.sourceId), 1) : '<p class="muted" style="font-size:12px">Исходный текст сохранён; структура появится после обработки.</p>'}</div>`;
    return `<div class="panel-body">${(d.history || [{ version: d.version, date: d.updated, live: d.live, change: "Текущий снимок источника ожидает обработки." }]).map((v) => `<div class="relation-card"><div class="chunk-top"><strong class="mono">v${v.version}</strong><span class="tag ${v.live ? "success" : ""}">${v.live ? "В индексе" : v.status === "Failed" ? "Failed" : "Не в индексе"}</span></div><p>${esc(v.change)}</p><small class="muted">${formatDate(v.date)}</small></div>`).join("")}<div class="inline-note">${icon("info", "small")}<span>В поиске — текущая успешно обработанная версия.</span></div></div>`;
  }
  function relationCard(f, chunks) {
    const sources = (f.sourceIds || []).map(sourceById).filter(Boolean);
    return `<article class="relation-card"><div class="chunk-top"><strong class="mono">${f.id}</strong>${tag(f.status)}</div><p>${esc(f.text)}</p>${f.reason ? `<p style="font-size:10px;color:var(--amber)">${esc(f.reason)}</p>` : ""}<div class="relation-links">Evidence:${f.chunkIds
      .filter((id) => chunks.some((c) => c.id === id))
      .map(
        (id) =>
          `<button class="text-button mono" data-action="select-chunk" data-chunk="${id}">${id}</button>`,
      )
      .join(
        " · ",
      )}<span>→</span>${f.entities.map((e) => `<span class="entity">${esc(e)}</span>`).join("")}<span>→ ${esc(f.topic)}</span></div><div class="relation-links">Sources: ${sources.map((s) => docLink(s.documentId, s.id + " · " + s.title, f.chunkIds.find((id) => chunkById(id)?.documentId === s.documentId) || "")).join(" · ") || "не указаны"}<span>· checked ${f.checkedAt ? formatDate(f.checkedAt) : "ещё не проверено"}</span></div></article>`;
  }

  const emptyContext = () => ({
    chunks: [],
    facts: [],
    sources: [],
    ok: false,
    reasons: [
      state.contextBusy
        ? "Контекст пересчитывается на сервере."
        : "Сначала выполните поиск.",
    ],
    payload: {},
    exclusions: [],
    estimatedTokens: 0,
  });
  function computeContext() {
    return state.context || emptyContext();
  }
  async function performSearch() {
    const revision = searchRevision;
    const result = await api("/api/search", {
      query: state.query,
      filters: state.filters,
      mode: state.mode,
    });
    if (revision !== searchRevision) return result;
    state.results = result;
    state.selected = new Set(result.selected_ids);
    state.context = result.context;
    state.answerReady = false;
    state.answer = null;
    return result;
  }
  async function api(path, body) {
    const controller = new AbortController();
    activeRequest?.abort();
    activeRequest = controller;
    const timeout = setTimeout(() => controller.abort(), 180000);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(state.editorToken ? { "X-Editor-Token": state.editorToken } : {}),
        },
        body: JSON.stringify(body),
        credentials: "omit",
        signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) {
        const error = new Error(
          data.error?.message || "Не удалось выполнить запрос.",
        );
        error.code = data.error?.code;
        throw error;
      }
      return data;
    } finally {
      clearTimeout(timeout);
      if (activeRequest === controller) activeRequest = null;
    }
  }
  async function refreshDB(paint = true) {
    const response = await fetch("/api/bootstrap", {
      cache: "no-store",
      credentials: "omit",
    });
    if (!response.ok)
      throw new Error("Не удалось прочитать Knowledge Base из PostgreSQL.");
    db = await response.json();
    if (!docById(state.documentId))
      state.documentId = db.documents[0]?.id || "";
    if (paint) render();
  }
  async function refreshContext() {
    if (!state.results) return;
    const revision = ++searchRevision;
    state.contextBusy = true;
    state.context = null;
    state.answer = null;
    state.answerReady = false;
    state.generating = false;
    render();
    try {
      const context = await api("/api/context", {
        run_id: state.results.runId,
        selected_ids: [...state.selected],
      });
      if (revision === searchRevision) state.context = context;
    } catch (error) {
      if (revision === searchRevision) state.error = error.message;
    } finally {
      if (revision === searchRevision) {
        state.contextBusy = false;
        render();
      }
    }
  }

  function sourceCard(s, index) {
    if (!s) return "";
    return `<div class="source-card"><div class="source-title"><span class="source-citation">${index}</span><div><strong>${docLink(s.documentId, s.title)}</strong><small>${esc(s.name)} · ${esc(s.id)} · ${formatDate(s.date)}</small></div></div><small>${s.external ? `<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)} ↗</a>` : esc(s.url)}</small>${s.snapshotHash ? `<div class="relation-links" style="margin-top:8px"><span class="mono">SHA-256: ${s.snapshotHash.slice(0, 12)}…</span><button class="text-button" data-action="download-source" data-source="${s.id}">Скачать выдержки</button></div>` : ""}</div>`;
  }
  function filterField(label, key, options) {
    return `<label class="field">${label}<select data-filter="${key}" ${state.searching ? "disabled" : ""}><option value="">Все</option>${options
      .map((o) => {
        const [value, title] = Array.isArray(o) ? o : [o, o];
        return `<option value="${esc(value)}" ${state.filters[key] === value ? "selected" : ""}>${esc(title)}</option>`;
      })
      .join("")}</select></label>`;
  }
  function renderSearch() {
    return (
      pageHead(
        "03 · Поиск",
        "RAG Search",
        "Поиск по фрагментам с фильтрами и оценкой релевантности.",
        button(icon("architecture") + "Как устроен поиск", "go-architecture"),
      ) +
      journey() +
      `
      <section class="panel"><form id="search-form" class="query-panel"><div class="query-label"><label for="rag-query">Что вы хотите узнать?</label><span class="tag">${icon("key", "small")} Только выбранные источники</span></div><textarea id="rag-query" maxlength="1000" required ${state.searching ? "disabled" : ""}>${esc(state.query)}</textarea><div class="query-controls"><div class="example-buttons"><button type="button" class="example-button" data-action="example-default" ${state.searching ? "disabled" : ""}>Снижение комиссии</button><button type="button" class="example-button" data-action="example-resources" ${state.searching ? "disabled" : ""}>Energy / Bandwidth</button><button type="button" class="example-button" data-action="example-ru" ${state.searching ? "disabled" : ""}>На русском</button><button type="button" class="example-button" data-action="example-low" ${state.searching ? "disabled" : ""}>Недостаток данных</button></div><button class="button primary" type="submit" ${state.searching ? "disabled" : ""}>${icon(state.searching ? "refresh" : "search", state.searching ? "spin" : "")}${state.searching ? "Поиск…" : "Выполнить поиск"}</button></div>
      <div class="filter-grid">${filterField("Language", "language", [...new Set(db.documents.map((d) => d.language))])}${filterField("Source", "source", [...new Set(db.documents.map((d) => d.source))])}${filterField("Topic", "topic", [...new Set(db.documents.map((d) => d.topic))])}${filterField("Entity", "entity", [...new Set(db.chunks.flatMap((c) => c.entities))])}${filterField(
        "Document",
        "document",
        db.documents.map((d) => [d.id, d.title]),
      )}<label class="field">Получено с<input type="date" data-filter="date" value="${esc(state.filters.date)}" ${state.searching ? "disabled" : ""}></label>${filterField("Verification status", "verification", ["Verified", "Unverified", "Outdated"])}<label class="field">Project / index<input readonly value="tpe · материалы в индексе" title="Один проект; исключённые из поиска документы не участвуют в выдаче."></label></div><div class="filter-foot"><span>${icon("filter", "small")} Metadata-фильтры применяются до отбора кандидатов</span><button type="button" class="text-button" data-action="clear-filters" ${state.searching ? "disabled" : ""}>Сбросить фильтры</button></div></form></section>
      <div id="search-output">${state.results ? searchOutput() : emptySearch()}</div>`
    );
  }
  function emptySearch() {
    return `<section class="panel"><div class="empty"><div class="empty-icon">${icon("search")}</div><h2>Введите вопрос</h2><p>Выберите пример или напишите свой вопрос.</p><span class="tag">Vector + Full-Text → RRF → Reranking → Context</span></div></section>`;
  }
  function searchOutput() {
    const r = state.results,
      c = computeContext();
    const needsLive =
      r.mode === "saved" && r.items.some((item) => !item.scored);
    return `${needsLive ? `<div class="alert info"><div><strong>Для этих фрагментов нет сохранённых оценок</strong><p>Выполните новый поиск через OpenAI. Расходуется баланс API.</p>${button("Выполнить поиск через OpenAI", "live-search", "primary")}</div></div>` : ""}<section class="panel"><details class="trace-details" open><summary><span>${icon("layers", "small")} Retrieval pipeline</span><span class="tag success">${r.items.length} результатов</span></summary><div class="trace-body"><div class="trace-steps">${[
      ["01", "Query understanding", r.info.intent],
      ["02", "Entities / filters", r.candidateCount + " candidates"],
      [
        "03",
        "Hybrid Search",
        r.vectorCount + " vector + " + r.ftsCount + " full-text",
      ],
      ["04", "RRF · k = 60", r.fusedCount + " unique candidates"],
      ["05", "Reranking", r.reranker],
      ["06", "Context Builder", c.chunks.length + " selected chunks"],
    ]
      .map(
        ([n, title, desc]) =>
          `<div class="trace-step"><span>${n}</span><strong>${title}</strong><small>${esc(desc)}</small></div>`,
      )
      .join(
        "",
      )}</div><div class="query-understanding"><div><small>Понятый intent</small><strong>${esc(r.info.intent)}</strong></div><div><small>Извлечённые сущности</small>${r.info.entities.map((e) => `<span class="entity">${e}</span>`).join(" ") || "Не определены"}</div><div><small>Ограничение корпуса</small><strong>${r.filters.language || "Все языки"} · tpe · live</strong></div></div><div class="inline-note">${icon("info", "small")}<span>${r.vectorModel ? "Vector: cosine similarity." : "Векторный поиск для этого запроса не выполнялся."} PostgreSQL FTS · ts_rank_cd; pgvector · cosine; Python · RRF. Reranker: ${esc(r.reranker)}.</span></div></div></details></section>
      <div class="results-layout"><section class="panel"><div class="panel-head"><div><h2>Найденные фрагменты <span class="tag" style="margin-left:5px">${r.items.length}</span></h2><p>Выберите не более шести фрагментов для контекста</p></div><span class="tag">Top ${r.items.length}</span></div>${r.items.length ? r.items.map((item, i) => resultCard(item, i + 1)).join("") : `<div class="empty"><div class="empty-icon">${icon("warning")}</div><h2>Подходящих фрагментов нет</h2><p>Попробуйте уточнить вопрос или расширить фильтры. Неподтверждённый ответ не будет сформирован.</p>${button("Расширить фильтры", "clear-filters", "secondary")}</div>`}</section><aside class="panel context-summary"><div class="panel-body"><h3>Пакет для AI</h3><p class="confidence-note">Только выбранные Verified-фрагменты.</p><div class="summary-row"><span>Selected chunks</span><strong>${c.chunks.length}</strong></div><div class="summary-row"><span>Verified facts</span><strong>${c.facts.length}</strong></div><div class="summary-row"><span>Sources</span><strong>${c.sources.length}</strong></div><div class="summary-line"></div><div class="confidence-label"><span>Достаточность данных</span><span class="tag ${c.ok ? "success" : "warning"}">${c.ok ? "Sufficient" : "Low"}</span></div><p class="confidence-note">${c.ok ? "Есть проверенные факты, источники и покрытие вопроса." : esc(c.reasons[0])}</p>${button("Посмотреть контекст " + icon("arrow"), "go-context", "primary")}${!c.ok ? button("Открыть Low Confidence", "go-low", "secondary") : ""}<div class="inline-note">${icon("shield", "small")}<span>Relevance — оценка соответствия запросу, а не вероятность истинности.</span></div></div></aside></div>`;
  }
  function resultCard(c, index) {
    const d = docById(c.documentId),
      allowed =
        c.status === "Verified" && c.scored && c.score >= LIMITS.relevance;
    return `<article class="result-card ${allowed ? "" : "excluded"}"><div class="result-top"><div class="result-title"><input type="checkbox" data-chunk-selection="${c.id}" aria-label="Включить ${c.id} в контекст" ${state.selected.has(c.id) ? "checked" : ""} ${!allowed ? "disabled" : ""}><span class="mono" style="color:#99a98d">${String(index).padStart(2, "0")}</span>${docLink(d.id, d.title, c.id)}</div><span class="score"><small>RELEVANCE</small>${c.scored ? c.score.toFixed(2) : "—"}</span></div><p class="result-text">“${esc(c.text)}”</p><div class="result-meta"><span class="mono">${esc(shortId(c.id))}</span><span>${esc(d.source)}</span><span>${d.language}</span><span>${formatDate(d.updated)}</span><span>v${d.version}</span>${tag(c.status)}</div>${!allowed ? `<p style="font-size:10px;color:var(--amber);margin-top:8px">Исключён из контекста: ${c.status !== "Verified" ? "сверьте фрагмент с источником" : !c.scored ? "нет сохранённой оценки; выполните поиск через OpenAI" : "релевантность ниже порога 0.70"}.</p>` : ""}<details class="ranking-details"><summary>Почему найден этот результат?</summary><p>Vector rank: ${c.vectorRank || "—"} · Full-Text rank: ${c.ftsRank || "—"} · RRF: <span class="mono">${c.rrf.toFixed(5)}</span><br>Совпадающие сущности: ${c.entities.map(esc).join(", ")}.</p></details></article>`;
  }
  function prerequisite(title) {
    return `<section class="panel"><div class="empty"><div class="empty-icon">${icon("search")}</div><h2>${title}</h2><p>Сначала выполните поиск.</p>${button("Перейти к RAG Search " + icon("arrow"), "go-search", "primary")}</div></section>`;
  }
  function renderContext() {
    const head =
      pageHead(
        "04 · Контекст",
        "Retrieved Context",
        "Фрагменты, факты и источники для ответа.",
        button("← К результатам", "go-search") +
          (state.results
            ? button(icon("download") + "Скачать JSON", "download-context")
            : ""),
      ) + journey();
    if (!state.results) return head + prerequisite("Сначала найдите знания");
    const c = computeContext();
    return (
      head +
      `<div class="context-heading">${icon("search")}<div><small>Вопрос</small><p>${esc(state.results.query)}</p></div></div>${!c.ok ? `<div class="alert">${icon("warning")}<div><strong>Confidence: Low · передача в AI заблокирована</strong><p>${esc(c.reasons.join(" "))}</p></div></div>` : ""}<div class="context-layout"><div><section class="panel"><div class="panel-head"><div><h2>Selected chunks <span class="tag">${c.chunks.length}</span></h2><p>Компактная выборка из ${liveDocs().reduce((n, d) => n + chunksFor(d).length, 0)} live-фрагментов базы</p></div><span class="tag success">Verified only</span></div>${c.chunks.length ? c.chunks.map((ch) => `<div class="chunk-card"><div class="chunk-top"><span class="mono">${esc(shortId(ch.id))}</span><span class="tag">Relevance ${ch.score.toFixed(2)}</span></div><p>${esc(ch.text)}</p><div class="chunk-bottom">${docLink(ch.documentId, docById(ch.documentId).title, ch.id)}<span>· v${docById(ch.documentId).version} · ${docById(ch.documentId).language}</span>${tag(ch.status)}</div></div>`).join("") : '<div class="empty"><p>Выбранных проверенных chunks нет.</p></div>'}</section><section class="panel"><div class="panel-head"><div><h2>Relevant facts <span class="tag">${c.facts.length}</span></h2><p>Только факты, подкреплённые выбранными chunks</p></div>${icon("shield")}</div><div class="panel-body">${c.facts.map((f, i) => `<div class="fact-item"><span class="fact-index">${i + 1}</span><div><span class="mono">${f.id}</span><p>${esc(f.text)}</p><small>Evidence: ${f.chunkIds.map((id) => docLink(chunkById(id).documentId, id, id)).join(" · ")} · checked ${formatDate(f.checkedAt)}</small></div></div>`).join("") || '<p class="muted" style="font-size:12px">Подтверждённых фактов для выбранных фрагментов нет.</p>'}</div></section><section class="panel"><details class="trace-details"><summary><span>Что исключено из контекста</span><span class="tag">${c.exclusions.length}</span></summary><div class="panel-body" style="padding-top:0">${c.exclusions.map((e) => `<div class="summary-row"><span class="mono">${e.id}</span><span>${esc(e.reason)}</span></div>`).join("") || '<p class="muted">Все найденные фрагменты включены.</p>'}<p class="confidence-note">В поиске участвует только текущая успешно обработанная версия документа в индексе.</p></div></details></section></div><aside><section class="panel"><div class="panel-head"><h2>Sources <span class="tag">${c.sources.length}</span></h2>${icon("link")}</div><div class="panel-body">${c.sources.map((s, i) => sourceCard(s, i + 1)).join("") || '<p class="muted" style="font-size:12px">Источники не определены.</p>'}</div></section><section class="panel"><div class="panel-body"><div class="confidence-label"><strong>Confidence</strong><span class="tag ${c.ok ? "success" : "warning"}">${c.ok ? "Sufficient" : "Low"}</span></div><p class="confidence-note">${c.ok ? "Выбранные факты и источники позволяют ответить на вопрос." : "Условий для обоснованного ответа недостаточно."}</p><div class="summary-line"></div><div class="budget-grid"><div><small>Оценка tokens*</small><div class="budget-value">~${c.estimatedTokens}</div></div><div><small>Лимит текста chunks</small><div class="budget-value">7 800 знаков</div></div></div><p class="confidence-note">* Приблизительно, по длине JSON. Не более 6 chunks и 7 800 знаков текста.</p><div class="summary-line"></div>${c.ok ? button(icon(state.generating ? "refresh" : "spark", state.generating ? "spin" : "") + (state.generating ? "Получение ответа…" : "Передать контекст AI"), "generate-answer", "primary", `style="width:100%" ${state.generating ? "disabled" : ""}`) : button("Посмотреть недостаток данных", "go-low", "secondary", 'style="width:100%"')}<div class="inline-note">${icon("info", "small")}<span>${state.results.mode === "live" ? "Ответ будет запрошен у OpenAI по выбранному контексту." : "Сохранённый ответ. Для нового ответа выберите Live OpenAI и повторите поиск."}</span></div></div></section><section class="panel"><details class="trace-details"><summary><span>Пакет для AI · JSON</span>${icon("context", "small")}</summary><div class="panel-body" style="padding-top:0">${button(icon("copy") + "Копировать JSON", "copy-context", "secondary")}<pre class="json-view">${esc(JSON.stringify(c.payload, null, 2))}</pre></div></details></section></aside></div>`
    );
  }
  function answerHTML(c) {
    const answer = state.answer;
    if (!answer) return "";
    const paragraphs = answer.paragraphs
      .map(
        (p) =>
          `<p>${esc(p.text)} ${p.chunk_ids
            .map((id) => {
              const ch = c.chunks.find((x) => x.id === id);
              if (!ch) return "";
              const d = docById(ch.documentId),
                number = c.sources.findIndex((s) => s.id === d.sourceId) + 1;
              return `<button class="citation" data-action="open-document" data-document="${esc(ch.documentId)}" data-chunk="${esc(id)}" aria-label="Открыть ${esc(id)}: ${esc(d.title)}">[${number}]</button>`;
            })
            .join("")}</p>`,
      )
      .join("");
    return (
      paragraphs +
      (answer.limitations.length
        ? `<div class="alert info"><div><strong>Что нужно проверить отдельно</strong>${answer.limitations.map((t) => `<p>${esc(t)}</p>`).join("")}</div></div>`
        : "")
    );
  }
  function renderAnswer() {
    const head =
      pageHead(
        "05 · Ответ",
        "AI Answer",
        "Ответ по выбранному контексту.",
        button("← Проверить контекст", "go-context") +
          (state.answerReady
            ? button(icon("copy") + "Копировать ответ", "copy-answer")
            : ""),
      ) + journey();
    if (!state.results)
      return head + prerequisite("Сначала подготовьте контекст");
    const c = computeContext();
    if (!c.ok)
      return (
        head +
        `<div class="alert">${icon("warning")}<div><strong>Ответ не сформирован: Confidence Low</strong><p>${esc(c.reasons.join(" "))}</p></div></div>${button("Открыть Low Confidence", "go-low", "primary")}`
      );
    if (!state.answerReady)
      return (
        head +
        `<section class="panel"><div class="empty"><div class="empty-icon">${icon("context")}</div><h2>Контекст готов к передаче</h2><p>${c.chunks.length} chunks · ${c.facts.length} verified facts · ${c.sources.length} sources. Проверьте пакет и сформируйте ответ.</p>${button("Проверить и передать контекст", "go-context", "primary")}</div></section>`
      );
    const usedSources = c.sources.filter((s) =>
      state.answer.paragraphs.some((p) =>
        p.chunk_ids.some(
          (id) => docById(chunkById(id).documentId).sourceId === s.id,
        ),
      ),
    );
    return (
      head +
      `<div class="question-card"><span class="eyebrow">Вопрос</span>${esc(state.results.query)}</div><div class="answer-layout"><section class="panel answer-panel"><div class="agent-title"><div class="agent-icon">${icon("spark")}</div><div><strong>Knowledge Agent</strong><small>${esc(state.answer?.model || "gpt-4.1-mini")} · ${state.answer.mode === "live" ? "Live OpenAI" : state.answer?.editorialReview ? "сохранённый ответ · проверен" : "сохранённый ответ"}</small></div><span class="tag success" style="margin-left:auto">Источники ответа</span></div><div class="answer-content" id="answer-text">${answerHTML(c)}</div><div class="answer-foot"><span class="confidence-note">Контекст: ${c.chunks.length} chunks · ${c.facts.length} facts</span>${button(icon("copy") + "Копировать", "copy-answer")}</div></section><aside><section class="panel"><div class="panel-head"><h2>Использованные источники</h2><span class="tag">${usedSources.length}</span></div><div class="panel-body">${c.sources.map((s, i) => (state.answer.paragraphs.some((p) => p.chunk_ids.some((id) => docById(chunkById(id).documentId).sourceId === s.id)) ? sourceCard(s, i + 1) : "")).join("")}</div></section><div class="hint-card"><span class="eyebrow">Ссылки на доказательства</span><h3 style="margin-top:9px">От ответа к статье</h3><p>Ответ → факт → chunk → section → версия статьи → источник.</p><div class="connector-list"><span class="tag success">Live versions</span><span class="tag success">Verified facts</span></div><p class="confidence-note">Непроверенные claims не использованы. Confidence показывает достаточность контекста, а не вероятность истинности текста.</p>${button("Смотреть пакет контекста", "go-context", "secondary")}</div></aside></div><div class="inline-note">${icon("info", "small")}<span>Ответ получен ${esc(new Date(state.answer.generatedAt).toLocaleString("ru-RU"))}. Цитаты ведут к использованным фрагментам.</span></div>`
    );
  }
  function renderLow() {
    const head =
      pageHead(
        "Недостаток данных",
        "Low Confidence",
        "Причины отказа и доступные источники.",
        button("← К поиску", "go-search"),
      ) + journey();
    if (!state.results)
      return (
        head +
        `<section class="panel"><div class="empty"><div class="empty-icon">${icon("warning")}</div><h2>Проверьте сценарий недостатка данных</h2><p>Вопрос о точной комиссии на завтра выходит за пределы подтверждённого контекста.</p>${button("Запустить сценарий", "example-refusal", "primary")}</div></section>`
      );
    const c = computeContext();
    if (c.ok)
      return (
        head +
        `<div class="alert info">${icon("check")}<div><strong>Для текущего вопроса данных достаточно</strong><p>Чтобы проверить отказ, запустите пример с вопросом о точной комиссии на завтра.</p></div></div>${button("Проверить отказ", "example-refusal", "primary")}${button("Вернуться к контексту", "go-context", "secondary", 'style="margin-left:10px"')}`
      );
    const possible = [
      ...new Set((state.results.items || []).map((ch) => ch.documentId)),
    ]
      .map(docById)
      .filter(Boolean)
      .slice(0, 3);
    if (!possible.length) possible.push(...liveDocs().slice(0, 3));
    return (
      head +
      `<div class="question-card"><span class="eyebrow">Вопрос</span>${esc(state.results.query)}</div><div class="context-layout"><section class="panel"><div class="low-hero"><div class="low-symbol">${icon("shield")}</div><span class="tag warning">Confidence: Low</span><h2>Недостаточно проверенной информации</h2><p>Ответ не сформирован. Найденных материалов недостаточно для запрошенного вывода.</p></div><div class="low-body"><h3 class="section-title">ЧЕГО НЕ ХВАТАЕТ</h3>${c.reasons.map((reason, i) => `<div class="low-reason"><strong>0${i + 1}</strong>${esc(reason)}</div>`).join("")}<div class="low-actions">${button("Уточнить вопрос", "refine-query", "primary")}${button("Изменить фильтры", "go-search")}${button(icon("plus") + "Добавить источник", "open-import")}</div><p class="confidence-note">Новая статья требует сверки с источником и повторного поиска.</p></div></section><aside><section class="panel"><div class="panel-head"><div><h2>Возможные материалы</h2><p>Кандидаты для изучения, а не доказательство ответа</p></div></div><div class="panel-body">${possible.length ? possible.map((d) => `<div class="possible-source"><div class="doc-icon">${icon("document", "small")}</div><div><strong>${docLink(d.id, d.title)}</strong><small>${esc(d.source)} · ${d.language} · v${d.version}</small></div></div>`).join("") : '<p class="muted" style="font-size:12px">При выбранных фильтрах подходящих материалов нет. Расширьте поиск или добавьте источник.</p>'}</div></section><div class="hint-card"><h3>Продолжить проверку</h3>${state.results.mode === "saved" && state.results.items.some((item) => !item.scored) ? `<p>Новые фрагменты нужно оценить через OpenAI.</p>${button("Выполнить поиск через OpenAI", "live-search")}` : `${button("Вернуться к результатам", "go-search")}${button("Использовать пример вопроса", "example-default-search")}`}</div></aside></div>`
    );
  }
  function renderArchitecture() {
    return (
      pageHead(
        "Архитектура",
        "Архитектура и решения",
        "Хранение, поиск и формирование ответа.",
        `<a class="button secondary" href="architecture.md" download>${icon("download")}Пояснения .md</a>` +
          button("Начать сценарий", "start-tour", "primary"),
      ) +
      `
    <section class="panel"><div class="panel-head"><h2>Реализовано в этой версии</h2></div><div class="panel-body"><div class="architecture-model"><div class="model-card"><h3>Python / FastAPI</h3><p>Единый async API: документы, обработка, RAG, контекст и OpenAI. Интерфейс получает данные из PostgreSQL. Ключ OpenAI хранится на сервере.</p></div><div class="model-card"><h3>PostgreSQL + pgvector</h3><p>Документы, версии и evidence-связи. pgvector cosine + PostgreSQL Full-Text → Python RRF → reranker → контекст. В БД сохраняются jobs, поисковые прогоны, ответы и лимиты.</p></div><div class="model-card"><h3>Проверка ответа</h3><p>Сервер заново собирает контекст из своего набора источников. Цитаты должны указывать на выбранные Verified chunks.</p></div></div></div></section>
    <section class="panel"><div class="panel-head"><div><h2>Knowledge Base → RAG → AI Agent</h2><p>Работающий сценарий Python/FastAPI + PostgreSQL/pgvector</p></div><span class="tag">Реализовано</span></div><div class="panel-body"><div class="architecture-flow" role="img" aria-label="Источники передают статьи через FastAPI в Knowledge Base на PostgreSQL и pgvector. RAG выполняет vector search и full-text search с metadata-фильтрами, объединяет результаты через RRF, ранжирует reranker-ом и формирует контекст. AI Agent использует только этот контекст и возвращает ответ с источниками либо отказ."><div class="arch-block"><span class="eyebrow">Хранение</span><h3>Knowledge Base</h3><p>Article / Section / Chunk<br>Fact / Claim / Entity / Topic / Source</p><div class="arch-inner"><span>PostgreSQL<br>данные и связи</span><span>pgvector<br>векторы</span></div><span class="tag">Source snapshots + versions</span></div><div class="arch-arrow">→</div><div class="arch-block"><span class="eyebrow">Поиск</span><h3>RAG</h3><p>Query understanding → entity extraction</p><div class="arch-inner"><span>Vector Search</span><span>Full-Text Search</span><span>Metadata filters</span></div><div class="arch-chain">RRF → Reranking → Context Builder</div><p>Selected chunks + verified facts + sources<br>Confidence gate / low-confidence path</p></div><div class="arch-arrow">→</div><div class="arch-block"><span class="eyebrow">Ответ</span><h3>AI Agent</h3><p>Контекст и инструкция<br>Источники в ответе<br>Отказ при нехватке данных</p><span class="tag">Ответ по выбранному контексту</span></div></div><div class="inline-note">${icon("architecture", "small")}<span>Источники → Ingestion Worker → FastAPI / Knowledge Service → PostgreSQL + pgvector. FastAPI оркестрирует RAG → Context Builder → Agent. Backend контролирует доступ к базе и секретам.</span></div></div></section>
    <section class="panel"><div class="panel-head"><h2>Что хранится и как связано</h2></div><div class="panel-body"><div class="architecture-model">${[
      [
        "Article → Version → Section → Chunk",
        "Снимок документа и его версии; каждый chunk связан с разделом и конкретной версией. В поиск идёт только live-версия.",
      ],
      [
        "Chunk ↔ Fact / Claim ↔ Source",
        "Утверждение имеет доказательства: chunk, источник, дата и статус проверки. Один факт может опираться на несколько источников.",
      ],
      [
        "Fact / Claim ↔ Entity ↔ Topic",
        "Утверждение связано с entities через many-to-many и относится к topic. Source и evidence связывают его с исходной версией документа.",
      ],
      [
        "Chunk → Embedding",
        "Вектор хранится с model, размерностью 256, input_hash и ссылкой на версию. Разные векторные пространства не смешиваются.",
      ],
      [
        "Project → Documents / Sources",
        "Прототип работает с одним проектом tpe. Другой project_id не принимается; изменения защищены паролем редактора. Полный multitenant RBAC — следующий этап.",
      ],
      [
        "Query → Retrieval Run → Context",
        "Сохраняются фильтры, ранги, выбранные chunks, версии и источники. Ответ можно проследить до входного контекста.",
      ],
    ]
      .map(
        ([title, text]) =>
          `<div class="model-card"><h3>${title}</h3><p>${text}</p></div>`,
      )
      .join("")}</div></div></section>
    <section class="panel"><div class="panel-head"><h2>Ключевые архитектурные решения</h2></div><div class="panel-body">${[
      [
        "01 · Один backend, разделённые обязанности",
        "Knowledge Base — логическая модель хранения и связей; PostgreSQL — СУБД; pgvector — расширение для векторов. RAG — сервис поиска и сборки контекста. AI Agent использует результат RAG, а не всю базу.",
      ],
      [
        "02 · Фильтрация перед отбором кандидатов",
        "project_id, language, source, document, date и live-status ограничивают оба поисковых запроса до top-N. Для ANN-поиска отдельно проверяем recall при фильтрах: iterative scan / over-fetch / partitions выбираются после измерений.",
      ],
      [
        "03 · Hybrid Search и RRF",
        "Vector search находит смысловое сходство, Full-Text — совпадение терминов. RRF объединяет ранги по формуле Σ 1/(k+rank), здесь k=60. Затем reranker оценивает пару query–chunk. RRF-score не превращается в confidence.",
      ],
      [
        "04 · Context Builder и достаточность знаний",
        "Из найденных фрагментов выбираются релевантные Verified chunks, поддержанные факты и их источники. В этой версии используется порог 0.70 и минимум 2 chunks / 2 facts плюс покрытие вопроса; это иллюстрация политики, требующая калибровки.",
      ],
      [
        "05 · Статус проверки и происхождение",
        "Processed означает успешную обработку, а не подтверждённую истинность. Автоматически извлечённые claims остаются Unverified. Проверка по источнику и при необходимости решение редактора меняют статус на Verified.",
      ],
      [
        "06 · Идемпотентность и история",
        "Повтор события или повторная обработка не создают дубликат документа. Все версии сохраняются; снятые с публикации материалы деактивируются в поиске. Полный экспорт CMS требует реконсиляции и защиты от неполного снимка.",
      ],
      [
        "07 · Управляемый путь Low Confidence",
        "Если источник, подтверждённые факты или покрытие вопроса отсутствуют, backend возвращает low_confidence и блокирует генерацию обоснованного ответа. Пользователь уточняет вопрос, меняет фильтры или добавляет источник.",
      ],
    ]
      .map(
        ([title, text]) =>
          `<div class="decision"><h3>${title}</h3><p>${text}</p></div>`,
      )
      .join("")}</div></section>
    <section class="panel"><div class="panel-head"><h2>Моменты для обсуждения</h2></div><div class="panel-body"><ul class="discussion"><li><strong>Кто и по каким правилам подтверждает facts / claims?</strong> Нужны политика надёжности источников, срок актуальности, работа с конфликтами и роль редактора.</li><li><strong>FTS или BM25?</strong> Native PostgreSQL Full-Text Search не является BM25. Для MVP достаточно FTS + pgvector + RRF; BM25 — отдельное решение при подтверждённой потребности.</li><li><strong>Как измерять confidence и retrieval quality?</strong> На 50–100 контрольных вопросах с эталонными документами оцениваем recall@k, релевантность, корректность ссылок и частоту обоснованных отказов. Порог reranker зависит от конкретной модели.</li><li><strong>Как обновляется индекс?</strong> Зафиксировать схему экспорта CMS, live/draft semantics, вебхуки, реконсиляцию удалений и обработку неполных выгрузок.</li><li><strong>Какой reranker и embedding model?</strong> Выбор влияет на стоимость, задержку, многоязычность и миграции. Источники сейчас на английском; вопросы и ответы могут быть на русском. Качество других языков проверяется отдельно.</li></ul></div></section>
    <section class="panel"><div class="panel-head"><h2>Словарь компонентов</h2></div><div class="panel-body"><div class="definition-grid">${[
      [
        "Knowledge Base",
        "Модель знаний: документы, факты, источники, связи и версии.",
      ],
      [
        "PostgreSQL",
        "Реляционное хранилище данных; также предоставляет полнотекстовый поиск.",
      ],
      [
        "pgvector",
        "Расширение PostgreSQL для хранения векторов и поиска ближайших соседей.",
      ],
      [
        "Embeddings",
        "Числовые представления текста, позволяющие сравнивать смысл в одном векторном пространстве.",
      ],
      [
        "RAG",
        "Поиск релевантных знаний и сборка ограниченного контекста для ответа.",
      ],
      [
        "AI Agent",
        "Исполнитель с инструкцией и Tools; формирует ответ на основе предоставленного контекста.",
      ],
    ]
      .map(
        ([title, text]) =>
          `<div class="definition"><strong>${title}</strong><p>${text}</p></div>`,
      )
      .join("")}</div></div></section>`
    );
  }
  let searchRevision = 0,
    activeRequest = null;
  function invalidateSearch() {
    activeRequest?.abort();
    searchRevision++;
    state.error = "";
    state.context = null;
    state.contextBusy = false;
    state.answer = null;
    state.results = null;
    state.selected = new Set();
    state.answerReady = false;
    state.searching = false;
    state.generating = false;
  }
  function setExample(kind) {
    invalidateSearch();
    state.query =
      kind === "low"
        ? db.lowQuery
        : kind === "ru"
          ? "Как снизить комиссию за перевод USDT TRC-20?"
          : kind === "resources"
            ? "How do Energy and Bandwidth work on TRON?"
            : db.defaultQuery;
    state.filters = {
      language: "EN",
      source: "",
      topic: "",
      entity: "",
      document: "",
      date: "",
      verification: "",
    };
  }
  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext)
        await navigator.clipboard.writeText(text);
      else {
        const area = document.createElement("textarea");
        area.value = text;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.append(area);
        area.select();
        if (!document.execCommand("copy")) throw new Error("copy unsupported");
        area.remove();
      }
      toast("Скопировано в буфер обмена.");
    } catch {
      toast(
        "Буфер обмена недоступен. Используйте скачивание JSON или выделите текст вручную.",
      );
    }
  }
  function download(filename, text, type = "application/json") {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function reset() {
    invalidateSearch();
    state.docTab = "structure";
    state.kbQuery = "";
    state.kbStatus = "";
    state.editImportId = null;
    setExample("default");
    await refreshDB(false);
    document.getElementById("import-dialog").close();
    navigate("kb");
    toast("Вид сброшен. Документы сохранены.");
  }
  async function importDocument() {
    if (state.importBusy) return;
    const dialog = document.getElementById("import-dialog");
    const title = document.getElementById("import-name");
    const url = document.getElementById("import-url");
    const topic = document.getElementById("import-topic");
    if (
      !title.reportValidity() ||
      !url.reportValidity() ||
      !topic.reportValidity()
    )
      return;
    const existing = state.editImportId ? docById(state.editImportId) : null;
    const input = {
      title: title.value.trim(),
      body: document.getElementById("import-body").value,
      url: url.value,
      language: document.getElementById("import-language").value,
      topic: topic.value.trim(),
    };
    state.importBusy = true;
    try {
      await requireEditor(dialog);
      const result = await api(
        existing
          ? "/api/documents/" + encodeURIComponent(existing.id) + "/retry"
          : "/api/documents",
        input,
      );
      dialog.close();
      invalidateSearch();
      await refreshDB(false);
      state.documentId = result.documentId;
      state.chunkId = "";
      state.docTab = "structure";
      navigate("document", result.documentId);
      toast("Статья сохранена. Обработка выполняется в фоне.");
    } finally {
      state.importBusy = false;
    }
  }
  async function runSearch() {
    if (state.searching) return;
    state.query =
      document.getElementById("rag-query")?.value.trim() || state.query.trim();
    if (!state.query) {
      toast("Введите вопрос.");
      return;
    }
    invalidateSearch();
    state.searching = true;
    const revision = searchRevision;
    render();
    try {
      const result = await performSearch();
      if (revision !== searchRevision) return;
      state.results = result;
    } catch (error) {
      if (revision === searchRevision)
        state.error =
          error.name === "AbortError"
            ? "Время ожидания истекло. Повторите запрос."
            : error.message;
    } finally {
      if (revision === searchRevision) {
        state.searching = false;
        render();
      }
    }
  }
  document.addEventListener("submit", async (event) => {
    if (event.target.id !== "search-form") return;
    event.preventDefault();
    await runSearch();
  });
  document.addEventListener("input", (event) => {
    const el = event.target;
    if (el.id === "kb-query") {
      state.kbQuery = el.value;
      document.getElementById("kb-rows").innerHTML = kbRows();
      document.getElementById("kb-row-count").textContent =
        `${filteredDocs().length} из ${db.documents.length} документов`;
    }
    if (el.id === "rag-query") {
      state.query = el.value;
      invalidateSearch();
      const out = document.getElementById("search-output");
      if (out) out.innerHTML = emptySearch();
    }
  });
  document.addEventListener("change", async (event) => {
    const el = event.target;
    if (el.id === "search-mode") {
      try {
        setMode(el.value);
      } catch (error) {
        showError(error);
      }
      render();
      return;
    }
    if (el.id === "kb-status") {
      state.kbStatus = el.value;
      render();
    }
    if (el.dataset.filter) {
      state.filters[el.dataset.filter] = el.value;
      invalidateSearch();
      render();
    }

    if (el.dataset.chunkSelection) {
      if (el.checked && state.selected.size >= LIMITS.selected) {
        el.checked = false;
        toast("Можно выбрать не более шести фрагментов.");
        return;
      }
      el.checked
        ? state.selected.add(el.dataset.chunkSelection)
        : state.selected.delete(el.dataset.chunkSelection);
      await refreshContext();
    }
  });
  document.addEventListener("click", async (event) => {
    if (event.target.closest(".skip-link")) {
      event.preventDefault();
      document.getElementById("main")?.focus();
      return;
    }
    const el = event.target.closest("[data-action]");
    if (!el) return;
    event.preventDefault();
    const action = el.dataset.action;
    if (el.disabled) return;
    const dialog = el.closest("dialog");
    if (dialog) {
      dialog.querySelector("[data-dialog-error]").hidden = true;
      dialog.querySelector("[data-dialog-status]").hidden = true;
    }
    el.disabled = true;
    try {
      if (action === "close-dialog") dialog.close();
      else if (action === "go-kb") navigate("kb");
      else if (action === "go-search") navigate("search");
      else if (action === "go-architecture") navigate("architecture");
      else if (action === "go-context") navigate("context");
      else if (action === "go-low") navigate("low");
      else if (action === "start-tour") {
        state.docTab = "structure";
        navigate("document", "DOC-001", "CHK-101");
      } else if (action === "open-document") {
        state.docTab = "structure";
        navigate("document", el.dataset.document, el.dataset.chunk);
      } else if (action === "select-chunk") {
        state.chunkId = el.dataset.chunk;
        state.docTab = "structure";
        render();
        document
          .getElementById(state.chunkId)
          ?.scrollIntoView({ block: "center", behavior: "smooth" });
      } else if (action === "document-tab") {
        state.docTab = el.dataset.tab;
        render();
        document.querySelector(".tab.active")?.focus({ preventScroll: true });
      } else if (action === "search-document") {
        invalidateSearch();
        state.filters.document = el.dataset.document;
        state.filters.language = docById(el.dataset.document).language;
        navigate("search");
      } else if (action === "open-import") {
        state.editImportId = null;
        document.getElementById("import-title").textContent = "Добавить статью";
        document.getElementById("import-name").value = "";
        document.getElementById("import-body").value = "";
        document.getElementById("import-url").value = "";
        document.getElementById("import-language").value = "EN";
        document.getElementById("import-topic").value = "Resource model";
        openDialog("import-dialog");
      } else if (action === "import-success") await importDocument();
      else if (action === "retry-document") {
        const d = docById(el.dataset.document);
        state.editImportId = d.id;
        document.getElementById("import-name").value = d.title;
        document.getElementById("import-url").value = d.url;
        document.getElementById("import-body").value = d.rawBody || "";
        document.getElementById("import-language").value = state.editImportId
          ? docById(state.editImportId).language
          : "EN";
        document.getElementById("import-topic").value = state.editImportId
          ? docById(state.editImportId).topic
          : "Resource model";
        document.getElementById("import-title").textContent =
          "Повторить обработку";
        openDialog("import-dialog");
      } else if (
        action === "example-default" ||
        action === "example-resources" ||
        action === "example-low" ||
        action === "example-ru"
      ) {
        setExample(action.replace("example-", ""));
        render();
        document.getElementById("rag-query")?.focus();
      } else if (action === "example-default-search") {
        setExample("default");
        navigate("search");
      } else if (action === "example-refusal") {
        setExample("low");
        await performSearch();
        navigate("low");
      } else if (action === "refine-query") {
        navigate("search");
        setTimeout(() => {
          const q = document.getElementById("rag-query");
          q?.focus();
          q?.select();
        }, 20);
      } else if (action === "clear-filters") {
        state.filters = {
          language: "",
          source: "",
          topic: "",
          entity: "",
          document: "",
          date: "",
          verification: "",
        };
        invalidateSearch();
        render();
      } else if (action === "generate-answer") {
        const context = computeContext();
        if (!context.ok) {
          navigate("low");
          return;
        }
        state.generating = true;
        state.error = "";
        const revision = searchRevision;
        render();
        try {
          const answer = await api("/api/answer", {
            run_id: state.results.runId,
            selected_ids: [...state.selected],
          });
          if (revision !== searchRevision) return;
          if (!answer.answerable) {
            state.context = { ...context, ok: false, reasons: answer.reasons };
            state.generating = false;
            navigate("low");
            return;
          }
          state.answer = answer;
          state.answerReady = true;
          state.generating = false;
          navigate("answer");
        } catch (e) {
          if (revision === searchRevision) {
            state.error =
              e.name === "AbortError"
                ? "Время ожидания истекло. Повторите запрос."
                : e.message;
            state.generating = false;
            render();
          }
        }
      } else if (action === "open-api") {
        document.getElementById("ai-mode").value = state.mode;
        openDialog("api-dialog");
      } else if (action === "connect-editor") {
        await authenticateEditor(
          dialog.querySelector("[data-editor-password]").value.trim(),
        );
        toast("Пароль проверен. Можно добавлять и проверять документы.");
      } else if (action === "disconnect-editor") {
        state.editorToken = "";
        state.editorAuthenticated = false;
        try {
          sessionStorage.removeItem("kb-python-editor");
        } catch {}
        render();
      } else if (action === "save-api") {
        const password = dialog
          .querySelector("[data-editor-password]")
          .value.trim();
        if (password) await authenticateEditor(password);
        setMode(document.getElementById("ai-mode").value);
        dialog.close();
        render();
      } else if (action === "live-search") {
        setMode("live");
        navigate("search");
        render();
        await runSearch();
      } else if (action === "toggle-live") {
        if (!state.editorAuthenticated) {
          document.getElementById("ai-mode").value = state.mode;
          openDialog("api-dialog");
          toast("Подключите редактора, затем повторите действие.");
          return;
        }
        const d = docById(el.dataset.document);
        await api("/api/documents/" + encodeURIComponent(d.id) + "/live", {
          live: !d.live,
        });
        invalidateSearch();
        await refreshDB();
      } else if (action === "review-chunk") {
        const chunk = chunkById(el.dataset.chunk),
          doc = docById(chunk.documentId),
          source = sourceById(doc.sourceId);
        state.reviewChunk = chunk.id;
        document.getElementById("review-text").textContent = chunk.text;
        document.getElementById("review-source").href = source.url;
        document.getElementById("review-source").textContent = source.url;
        document.getElementById("review-note").value = "";
        document.getElementById("review-checked").checked = false;
        openDialog("review-dialog");
      } else if (action === "verify-chunk") {
        const note = document.getElementById("review-note"),
          checked = document.getElementById("review-checked");
        if (!note.reportValidity() || !checked.reportValidity()) return;
        await requireEditor(dialog);
        await api(
          "/api/chunks/" + encodeURIComponent(state.reviewChunk) + "/verify",
          { note: note.value, checked_against_source: checked.checked },
        );
        document.getElementById("review-dialog").close();
        invalidateSearch();
        await refreshDB();
        toast(
          "Проверка сохранена. Фрагмент доступен для формирования контекста.",
        );
      } else if (action === "download-source") {
        const source = db.sources.find((s) => s.id === el.dataset.source);
        if (source)
          download(
            source.id + "-excerpts.json",
            JSON.stringify(
              {
                source,
                excerpts: db.chunks
                  .filter((c) => c.documentId === source.documentId)
                  .map(({ embedding, ...c }) => c),
              },
              null,
              2,
            ),
          );
      } else if (action === "download-context")
        download(
          "rag-context.json",
          JSON.stringify(computeContext().payload, null, 2),
        );
      else if (action === "copy-context")
        copyText(JSON.stringify(computeContext().payload, null, 2));
      else if (action === "copy-answer") {
        const c = computeContext();
        const container = document.createElement("div");
        container.innerHTML = answerHTML(c);
        copyText(
          state.results.query +
            "\n\n" +
            container.innerText +
            "\n\nИсточники:\n" +
            c.sources
              .map(
                (s, i) => `[${i + 1}] ${s.title} — ${s.url} (снимок источника)`,
              )
              .join("\n"),
        );
      } else if (action === "reset") await reset();
    } catch (error) {
      showError(error, dialog || document.querySelector("dialog[open]"));
    } finally {
      el.disabled = false;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Enter" &&
      event.target.matches("[data-editor-password]")
    ) {
      event.preventDefault();
      event.target
        .closest("dialog")
        .querySelector('[data-action="connect-editor"]')
        .click();
      return;
    }
    if (
      !event.target.matches('[role="tab"]') ||
      !["ArrowLeft", "ArrowRight"].includes(event.key)
    )
      return;
    event.preventDefault();
    const tabs = [...document.querySelectorAll('[role="tab"]')],
      index = tabs.indexOf(event.target);
    tabs[
      (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
        tabs.length
    ].click();
  });
  window.addEventListener("hashchange", route);
  window.KB_LAB = {
    getSnapshot: () => ({
      screen: state.screen,
      documents: db.documents,
      results: state.results,
      context: computeContext(),
      answer: state.answer,
      mode: state.mode,
      editorAuthenticated: state.editorAuthenticated,
      error: state.error,
    }),
    reset,
  };
  route();
  if (state.editorToken)
    authenticateEditor(state.editorToken).catch(() => {
      state.editorToken = "";
      state.editorAuthenticated = false;
      try {
        sessionStorage.removeItem("kb-python-editor");
      } catch {}
      render();
    });
  setInterval(() => {
    if (
      db.documents.some((d) => ["Queued", "Processing"].includes(d.job?.status))
    )
      refreshDB().catch(showError);
  }, 700);
})();
