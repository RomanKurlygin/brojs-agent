# Шпаргалка для защиты проекта

Этот файл — краткий конспект, чтобы на защите уверенно объяснить, как устроен `brojs-agent-main`: где "мозг", как запускается, что делают ноды, как парсится Journal MCP и где лежат промпты.

---

## 1) Что делает проект

Проект автоматизирует сдачу домашних заданий курса KFU-26-1:

1. Берет задания из BroJS Journal (MCP).
2. Генерирует решение (код или текст, в зависимости от типа задания).
3. Создает/обновляет репозиторий в Gitea.
4. Отправляет ссылку в журнал (`task_update_answer`) и затем делает `task_submit`.
5. Если есть замечания, запускает режим пересдачи.

---

## 2) Точки входа и запуск

### Основные входы

- `agent.py` — экспортирует графы для LangGraph CLI.
- `src/agent/agent.py` — собирает агентов (оркестратор, первая сдача, пересдача).
- `src/agent/graph/pipeline.py` — пакетный граф прохождения всех задач.

### Как запускать

1. Установить зависимости:
   - `pip install -r requirements.txt`
2. Заполнить `.env` (минимум: `JOURNAL_TOKEN`, `GITEA_TOKEN`, `GITEA_OWNER`, опционально `OPENAI_API_KEY`).
3. Запуск через Studio:
   - `langgraph dev --allow-blocking --port 2024`
4. Либо запуск пайплайна программно:
   - импорт `pipeline` из `src/agent/graph/pipeline.py` и `await pipeline.ainvoke(...)`.

---

## 3) Где "мозг проекта"

У проекта 3 ключевых "мозга", все собираются в `src/agent/agent.py`:

1. `agent` — главный оркестратор:
   - не решает все руками,
   - делегирует задачи субагентам через tool `task`.
2. `homework_direct_agent` — первая сдача:
   - получает текст задания,
   - делает репозиторий и файлы,
   - отправляет ответ и submit.
3. `rework_agent` — пересдача:
   - берет существующий репозиторий,
   - правит по комментариям преподавателя,
   - повторно отправляет.

Почему это "мозг": именно здесь задаются модель, инструменты, middleware, память и субагенты.

---

## 4) Ноды LangGraph и их смысл

Граф находится в `src/agent/graph/pipeline.py`.

Последовательность:

- `fetch_tasks`
  - вызывает `tasks_list` из Journal MCP,
  - парсит список задач,
  - оставляет только `todo`/`in_progress`.
- `process_one_task`
  - берет текущую задачу,
  - определяет режим:
    - есть `answer.content` с URL репо -> пересдача (`rework_agent`),
    - нет URL -> первая сдача (`homework_direct_agent`),
  - после первой сдачи делает верификацию репозитория (`_verify_repo`),
  - при проблемах запускает retry с fix-подсказкой.
- `route`
  - если задачи еще остались -> снова `process_one_task`,
  - иначе -> `END`.

Состояние графа (`PipelineState`):
- `tasks` — очередь задач,
- `current_index` — индекс текущей задачи,
- `results` — успешные итоги,
- `errors` — ошибки.

---

## 5) Из чего состоят агенты

Каждый агент строится через `create_deep_agent` и включает:

- `model` — LLM из `src/agent/llm.py`,
- `tools` — набор инструментов (Journal MCP, Gitea, git, web),
- `system_prompt` — инструкция из `src/agent/prompts.py`,
- `backend` — виртуальная ФС (`CompositeBackend`):
  - workspace для работы с файлами,
  - skills, смонтированные в `/skills/`,
- `middleware`:
  - `SanitizeToolCallsMiddleware` — фильтр/нормализация вызовов tools,
  - `ValidateJournalWorkflowMiddleware` — контроль порядка `task_update_answer` перед `task_submit`.

---

## 6) Как парсится Journal MCP

Модуль: `src/agent/mcp_client.py` + вспомогательные функции в `pipeline.py`.

### Что происходит

1. MCP-клиент подключается к:
   - `https://platform.brojs.ru/jrnl-bh/api/mcp`
   - с `Authorization: Bearer JOURNAL_TOKEN`.
2. Инструменты загружаются динамически через `MultiServerMCPClient`.
3. Им добавляется префикс:
   - `mcp__journal-bh-professor__...`
4. Ответы MCP часто приходят как список блоков (`type="text"`).
   - `_parse_text()` достает текст из таких блоков.
5. Для списка задач:
   - `_parse_tasks()` делает `json.loads(...)`,
   - собирает `TaskInfo(id, title, status)`.

Итог: пайплайн работает со структурированными задачами, даже если исходный ответ был "сырой" текст из MCP.

---

## 7) Где лежат промпты

Все системные промпты в `src/agent/prompts.py`:

- `main_agent_instructions` — для оркестратора.
- `homework_doing_instructions` — для первой сдачи.
- `rework_instructions` — для пересдачи.
- `journal_tasks_submissions_instructions` — для journal-субагента.
- `research_instructions` — для web-субагента.

Ключевая мысль для защиты: поведение проекта задается не только кодом, но и промпт-контрактами (порядок действий, запреты, требования автопроверки).

---

## 8) LangChain / LangGraph / deepagents — роли

- `LangGraph`:
  - формализует бизнес-процесс (ноды, переходы, состояние) для пакетной обработки задач.
- `LangChain`:
  - сообщения (`HumanMessage`), модель (`ChatOpenAI`), tool-интеграция.
- `deepagents`:
  - удобная сборка мультиагентной системы:
    - субагенты,
    - память,
    - виртуальная файловая система,
    - middleware.

То есть:
- LangChain = "кирпичи",
- LangGraph = "процесс/оркестрация",
- deepagents = "готовая архитектурная обертка".

---

## 9) LLM-конфиг и fallback

`src/agent/llm.py`:

- если есть `OPENAI_API_KEY` -> используется OpenRouter (`https://openrouter.ai/api/v1`);
- иначе fallback на BroJS inference (`https://platform.brojs.ru/jrnl-bh/api/inference/v1`) с `JOURNAL_MCP_PAT` или `JOURNAL_TOKEN`.

Это важно для автопроверки: код может работать даже без локального `localhost`-сервиса.

---

## 10) Что часто спрашивают на защите

1. Почему разделили на оркестратор + direct + rework?
   - Чтобы разделить ответственность: роутинг, первая сдача, пересдача.
2. Зачем middleware?
   - Защита от неверных вызовов tools и от неправильного workflow в журнале.
3. Почему есть retry в pipeline?
   - Чтобы автоматически исправлять типовые ошибки автопроверки до финальной отправки.
4. Как различаете coding/non-coding?
   - По эвристике заголовка (`_CODING_KW`, `_NON_CODING_KW`) + разные правила верификации файлов.
5. Где хранится состояние между шагами?
   - В `PipelineState` для графа и в памяти/контексте агента (`AGENTS.md`) для deepagents.

---

## 11) Минимальная карта файлов

- `agent.py` — экспорт графов.
- `src/agent/agent.py` — сборка агентов (основной мозг).
- `src/agent/graph/pipeline.py` — ноды и цикл обработки задач.
- `src/agent/prompts.py` — системные промпты.
- `src/agent/mcp_client.py` — Journal MCP клиент и загрузка toolsets.
- `src/agent/llm.py` — единый LLM-конфиг.
- `src/agent/gitea_tools.py` — работа с Gitea API.
- `src/agent/tools.py` — git/web инструменты.
- `src/agent/middlewares/` — правила безопасности вызовов.

---

## 12) Коротко, как объяснить проект за 30 секунд

"Это LangGraph + multi-agent система для автоматизации сдачи ДЗ в BroJS.  
Pipeline берет задачи из Journal MCP, для каждой выбирает первую сдачу или пересдачу, агент создает/правит репозиторий в Gitea, отправляет ссылку в журнал и submit.  
Поведением управляют системные промпты и middleware, а надежность обеспечивается верификацией репозитория и retry-циклом."

