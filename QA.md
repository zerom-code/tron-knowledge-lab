# Проверки

Проверено на Python 3.12, PostgreSQL 16 / pgvector 0.8.2 и Chromium,
в Linux и Docker. Последнее обновление интерфейса: 10 октября 2026 года.

| Набор | Результат | Область |
|---|---|---|
| pytest | 25 passed | Парсер, RRF, SQL retrieval, фильтры, evidence, доступ редактора, схемы и квоты |
| Основной браузерный сценарий | 26 passed | Шесть экранов, ссылки, JSON, отказ, фильтры, mobile 390 px, ошибки JavaScript |
| Браузерный сценарий редактора | 19 passed | Ошибки внутри формы, пароль, Enter, импорт, разделы, сверка, Saved/Live, новый ответ OpenAI и архивирование |
| Failed/retry в браузере | 3 passed | Пустой текст, ошибка обработки, новая версия того же документа |
| Live workflow | 13 passed | Failed → retry → embeddings → review → поиск → ответ → archive |
| Live smoke | 6 passed | Embedding, reranking, контекст, новый ответ и проверка цитат |
| Docker Compose | Passed | Сборка, новая БД, миграции, seed, health и Saved без ключа OpenAI |

`verification/` содержит отчёты и снимки экранов. Метки времени в JSON
фиксируют время каждого прогона: некоторые backend Live-проверки выполнены
до обновления интерфейса. Исторические результаты модели не переписываются.
Повторные запуски скриптов пишут в игнорируемую папку `artifacts/qa/`.

## Без новых вызовов OpenAI

После запуска приложения:

```powershell
docker compose exec api python -m pytest -q
```

Тесты используют PostgreSQL и сохранённые результаты. Проверяются оба SQL-пути,
поддельные IDs, авторитетный контекст, изменение доступности документа и доступ
редактора, включая отказ при шаблонном пароле.

Для браузерных тестов нужен Python 3.12 с Playwright на машине запуска:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts\browser_test.py
.\.venv\Scripts\python.exe scripts\editor_test.py
```

Для editor_test требуется собственный `EDITOR_TOKEN` в `.env`. Он импортирует
два текста начального корпуса с переиспользованием embeddings, сверяет их
с сохранённым источником и оставляет документ архивированным. Без флага Live
проверяется 16 условий; с Live — 19. Служебный документ виден в истории базы.

`PROTOTYPE_ORIGIN` позволяет изменить адрес приложения; по умолчанию
http://127.0.0.1:8000 . `BROWSER_EXECUTABLE` задаёт путь к установленному Chromium.

## С вызовами OpenAI

Повторение opt-in сценариев расходует баланс API. Сервер и тестовая машина
должны использовать одинаковый пароль редактора. Серверу нужен OpenAI-ключ.

```powershell
$env:RUN_LIVE_TESTS = "1"
.\.venv\Scripts\python.exe scripts\editor_test.py
.\.venv\Scripts\python.exe scripts\workflow_test.py
Remove-Item Env:RUN_LIVE_TESTS
```

Editor Live проверяет новый ответ через кнопки интерфейса. Workflow отдельно
проверяет ошибку обработки, retry с сохранением Article, новый embedding,
проверку chunks и facts, поиск и ответ по импортированному источнику.

Новые chunks не становятся Verified автоматически. После review факты имеют
evidence-связи; ответ проходит проверку каждого абзаца по его собственным
цитатам. Эти проверки не доказывают истинность или актуальность источника.

## Поставка

```powershell
py scripts\package_project.py
```

Скрипт создаёт публичный архив для GitHub и полный архив с личной инструкцией
в игнорируемой папке `private/`. Упаковка использует список разрешённых файлов,
проверяет значения, похожие на API-ключи, целостность ZIP и записывает SHA-256.
`.env`, `.dev.vars`, БД, секреты, виртуальное окружение и вложения HR исключены.
Приложение раздаёт только `static/`; приватные пути проверены тестами.

## Ограничения проверки

Начальный корпус состоит из четырёх документов. Нагрузочный тест и калибровка
confidence на большом наборе вопросов не выполнены. Проверка моделью может
ошибаться. Полный RBAC, multitenancy и проект V1 не входят в этот прототип.
Нативный запуск на физическом Windows проверяет получатель; поставляемый
способ запуска Windows — Docker Desktop с Linux containers.
