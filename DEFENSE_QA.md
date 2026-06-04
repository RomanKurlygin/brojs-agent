# Вопросы преподавателя и ответы (защита brojs-agent)

Краткие формулировки для устного ответа. При необходимости указывай файлы в коде.

---

## 1. Общие вопросы о проекте

### В чём суть проекта?

**Ответ:** brojs-agent автоматизирует сдачу домашних заданий курса KFU-26-1: берёт задачи из BroJS Journal (MCP), генерирует решение, публикует в Gitea (`git.brojs.ru/<логин>/task-<id>`), отправляет ссылку в журнал (`task_update_answer` → `task_submit`). При отклонении — пересдача через `rework_agent`.

### Чем это отличается от «просто ChatGPT»?

**Ответ:** Это не чат ради ответа. Есть фиксированный workflow, реальные API (Journal, Gitea), проверка репозитория, middleware на порядок submit, пакетный LangGraph-pipeline и разделение ролей на агентов.

### Какие режимы запуска?

**Ответ:**
- **`agent`** — интерактивный оркестратор (делегирует субагентам).
- **`pipeline`** — пакетная обработка всех `todo`/`in_progress` заданий.
- **`homework_direct_agent` / `rework_agent`** — прямое выполнение одной сдачи или пересдачи (используются из pipeline и могут вызываться отдельно).

Точка входа для Studio: `langgraph.json` → `agent.py`.

### Есть ли у проекта свой UI?

**Ответ:** Отдельного веб-приложения в репозитории нет. Интерфейсы: LangGraph Studio (`langgraph dev`), терминал, плюс внешние UI Journal и Gitea.

---

## 2. Архитектура и агенты

### Где «мозг» проекта?

**Ответ:**
- `src/agent/agent.py` — сборка трёх агентов и субагентов.
- `src/agent/graph/pipeline.py` — бизнес-процесс очереди заданий.
- `src/agent/prompts.py` — правила поведения (порядок tools, coding/non-coding, автопроверка).
- `src/agent/mcp_client.py`, `gitea_tools.py`, `tools.py` — интеграции.

### Зачем три агента, а не один?

**Ответ:**
- **`agent`** — маршрутизация и делегирование (чат).
- **`homework_direct_agent`** — полный цикл первой сдачи (все tools сразу).
- **`rework_agent`** — другой промпт и сценарий: clone → правки → push, без создания нового репо.

Разделение снижает путаницу в промптах и ошибки модели.

### Что такое субагенты и зачем `task`?

**Ответ:** У оркестратора (`deepagents`) субагенты: journal, homework_doing, web_search. Вызываются через встроенный tool `task`. Оркестратор не держит все journal-tools одновременно в одном контексте — проще управлять.

### Чем LangGraph отличается от deepagents?

**Ответ:**
- **LangGraph** (`pipeline`) — жёсткий граф: ноды, state, цикл по заданиям.
- **deepagents** — multi-agent обёртка: субагенты, VFS, память `AGENTS.md`, tool-loop LLM.

LangGraph = процесс; deepagents = исполнители внутри шагов.

---

## 3. Pipeline (код)

### Какие ноды в pipeline и что делают?

**Ответ:** `src/agent/graph/pipeline.py`:
1. **`fetch_tasks`** — `tasks_list`, парсинг, фильтр `todo`/`in_progress`.
2. **`process_one_task`** — одно задание: homework или rework + verify + retry.
3. **`route`** — если `current_index < len(tasks)` → снова `process_one_task`, иначе END.

### Что в `PipelineState`?

**Ответ:** `tasks`, `current_index`, `results`, `errors` — очередь, указатель, успехи и ошибки по заданиям.

### Как выбирается первая сдача или пересдача?

**Ответ:** `_existing_repo_url(task_id)` читает `task_get` / answer: если в `answer.content` уже URL репозитория на `git.brojs.ru/<GITEA_OWNER>/` → `rework_agent`, иначе `homework_direct_agent`.

### Что делает `_verify_repo`?

**Ответ:** Через Gitea API проверяет файлы в репозитории до финальной сдачи (для новых сдач): наличие `main.py`/`requirements.txt` (coding) или markdown-ответа (non-coding), длина контента, отсутствие `localhost:1234`, `api_key="fake"`, наличие `build_*` в коде — типичные причины падения автопроверки.

### Сколько retry?

**Ответ:** `MAX_RETRIES = 2` в pipeline: после неудачной верификации агент получает `_fix_prompt` и повторяет `homework_direct_agent`.

### Как определяется coding vs non-coding?

**Ответ:** Эвристика `_is_coding(task)` по заголовку: списки `_CODING_KW` и `_NON_CODING_KW` (ai-fluency, эссе и т.д.). От типа зависят ожидаемые файлы в `_verify_repo` и текст fix-prompt.

---

## 4. Journal MCP и парсинг

### Как подключается журнал?

**Ответ:** `mcp_client.py`: HTTP MCP `https://platform.brojs.ru/jrnl-bh/api/mcp`, заголовок `Authorization: Bearer JOURNAL_TOKEN`. Инструменты переименовываются в `mcp__journal-bh-professor__<имя>`.

### Как парсится ответ `tasks_list`?

**Ответ:**
1. MCP часто возвращает список блоков `{type: "text", text: "..."}`.
2. `_parse_text()` достаёт строку.
3. `_parse_tasks()` делает `json.loads` и собирает `TaskInfo(id, title, status)`.

### Почему `task_update_answer` перед `task_submit`?

**Ответ:** Требование API журнала: без answer submit падает с «answer is empty». Закреплено в промптах и в `ValidateJournalWorkflowMiddleware`.

---

## 5. Промпты и поведение LLM

### Где лежат промпты?

**Ответ:** `src/agent/prompts.py`: `main_agent_instructions`, `homework_doing_instructions`, `rework_instructions`, journal и web субагенты.

### Почему «один tool за шаг»?

**Ответ:** Модель реже делает параллельные несовместимые вызовы; проще отлаживать и меньше race conditions в workflow.

### Как задаётся сценарий первой сдачи?

**Ответ:** В `homework_doing_instructions`: `task_text` → план → `gitea_create_repo` → `gitea_write_file` (по файлу) → `task_update_answer` (link) → `task_submit`.

---

## 6. Middleware и надёжность

### Зачем `SanitizeToolCallsMiddleware`?

**Ответ:** Отсекает вызовы tools с именами, которых нет в whitelist для данного агента — чтобы галлюцинация имени tool не ломала граф.

### Зачем `ValidateJournalWorkflowMiddleware`?

**Ответ:** Блокирует `task_submit`, если в истории сообщений не было `task_update_answer` для того же `taskId`.

---

## 7. LLM и конфигурация

### Откуда берётся LLM?

**Ответ:** `src/agent/llm.py`, один `ChatOpenAI` на всех агентов:
- при `OPENAI_API_KEY` → OpenRouter (`https://openrouter.ai/api/v1`);
- иначе fallback на BroJS inference (`JOURNAL_TOKEN` / `JOURNAL_MCP_PAT`).

Модель по умолчанию: `openai/gpt-oss-20b:free` (можно переопределить через env).

### Что такое rate limit (429)?

**Ответ:** OpenRouter ограничивает частоту запросов на free-модели. Длинный прогон агента (много шагов LLM) может упираться в лимит. Решение: пауза, другая модель, свой ключ.

### Где хранятся секреты?

**Ответ:** `.env` (не в git): `OPENAI_API_KEY`, `JOURNAL_TOKEN`, `GITEA_TOKEN`, `GITEA_OWNER`.

---

## 8. Gitea и git

### Как называются репозитории?

**Ответ:** `task-<taskId>`, URL: `https://git.brojs.ru/<GITEA_OWNER>/task-<id>`.

### Зачем и Gitea API, и git tools?

**Ответ:** Первая сдача часто через `gitea_write_file` (коммит на сервере). Пересдача — `git_clone`, правки в workspace, `git_push`. Разные сценарии в промптах.

---

## 9. Запуск и эксплуатация

### Появилось новое задание — что делать?

**Ответ:**
1. Проверить `.env`.
2. Запустить `pipeline` (команда из README или `langgraph dev` → граф `pipeline`).
3. Проверить статус в Journal и репозиторий на Gitea.

### Преподаватель отклонил — что делать?

**Ответ:** Снова запустить pipeline: для задания с URL в answer сработает `rework_agent` с комментариями из `task_get`.

### Что если Journal MCP не загрузился (0 tools)?

**Ответ:** Проверить `JOURNAL_TOKEN`, сеть, доступность `platform.brojs.ru`. Без journal tools pipeline не получит список заданий; Gitea/git часть может работать отдельно в ручном режиме.

---

## 10. Сравнение и критика

### Чем ваш проект отличается от форка одногруппника (Emil)?

**Ответ:** Общая архитектура похожа (те же 3 агента, pipeline, MCP, Gitea). Отличия: свои доработки в `pipeline.py` (verify, coding/non-coding по заголовку, retry), свои промпты, `GITEA_OWNER` из env, опционально `console.py`. У Emil в репозитории есть папка `scripts/` для CLI-демо — у вас её может не быть, это не ядро.

### Какие ограничения проекта?

**Ответ:**
- Зависимость от LLM и rate limits.
- Эвристика coding/non-coding по заголовку, не идеальный классификатор.
- Качество решения зависит от промпта и модели; автопроверка ловит типовые ошибки, но не гарантирует зачёт по смыслу.
- Нет собственного UI для конечного пользователя.

### Что бы улучшили дальше?

**Ответ:** CLI `scripts/` (health_check, demo_one_task), классификация типа задания по полному тексту ТЗ (как у Emil `_expects_code_repo`), явный `build_llm()` в `llm.py`, логирование токенов, очередь с приоритетами.

---

## 11. Вопросы «покажите в коде»

| Вопрос | Куда смотреть |
|--------|----------------|
| Сборка графа pipeline | `pipeline.py`, конец файла: `StateGraph`, `compile()` |
| Три агента | `agent.py`, `create_deep_agent` |
| Промпт первой сдачи | `prompts.py` → `homework_doing_instructions` |
| Middleware submit | `middlewares/validate_journal_workflow.py` |
| Префикс MCP tools | `mcp_client.py` → `_rename_tools` |
| ID курса | `constants.py` → `COURSE_ID` |

---

## 12. Одна фраза — запасной ответ на любой сложный вопрос

«В этом месте решение разделено на слой процесса (LangGraph pipeline), слой исполнения (deepagents + tools) и слой правил (prompts + middleware); конкретно ваш вопрос относится к …» — и называешь файл из таблицы выше.
