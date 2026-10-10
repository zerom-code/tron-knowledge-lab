(async () => {
  try {
    const responses = await Promise.all([
      fetch("/api/bootstrap", { cache: "no-store" }),
      fetch("/api/health", { cache: "no-store" }),
    ]);
    if (responses.some((r) => !r.ok))
      throw new Error("Python API или PostgreSQL недоступны.");
    [window.KB_DATA, window.KB_HEALTH] = await Promise.all(
      responses.map((r) => r.json()),
    );
    const script = document.createElement("script");
    script.src = "/app.js";
    document.head.append(script);
  } catch (error) {
    const container = document.getElementById("app");
    container.replaceChildren();
    const title = document.createElement("h1");
    title.textContent = "Не удалось открыть Knowledge Base";
    const message = document.createElement("p");
    message.textContent =
      error.message + " Проверьте запуск Docker Compose и обновите страницу.";
    container.append(title, message);
  }
})();
