const $ = (sel) => document.querySelector(sel);

const QUICK_PROMPTS = [
  "Какие субагенты у тебя есть и что каждый умеет?",
  "Покажи список заданий курса KFU-26-1",
  "Какие задания ещё не сданы?",
  "Создай репозиторий test-ui-check на Gitea (пустой README) и удали не нужно — только проверь доступ",
];

let threadId = `ui-${Date.now().toString(36)}`;
let logEventSource = null;
let pipelinePollTimer = null;

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function appendLog(entry) {
  const el = document.createElement("div");
  el.className = `log-line ${entry.level || "info"}`;
  el.innerHTML = `<span class="time">${formatTime(entry.ts)}</span><span class="msg">${escapeHtml(entry.message)}</span>`;
  const stream = $("#log-stream");
  stream.appendChild(el);
  stream.scrollTop = stream.scrollHeight;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderStatus(data) {
  const env = data.env || {};
  const grid = $("#status-grid");
  const cards = [
    { key: "llm", probe: null },
    { key: "journal", probe: "journal" },
    { key: "gitea", probe: "gitea" },
    { key: "tavily", probe: null },
  ];

  grid.innerHTML = cards
    .map(({ key, probe }) => {
      const item = env[key] || {};
      const ok = item.ok;
      const dot = ok ? "ok" : item.optional ? "warn" : "bad";
      let extra = "";
      if (key === "llm" && item.model) extra = `<div class="value">${item.model}</div>`;
      if (key === "gitea" && item.owner) extra = `<div class="value">@${escapeHtml(item.owner)}</div>`;
      const probeBtn = probe
        ? `<button type="button" class="btn btn-ghost btn-sm probe-btn" data-probe="${probe}">Проверить</button>`
        : "";
      return `
        <article class="status-card">
          <h3>${item.label || key}</h3>
          <div class="value">
            <span class="status-dot ${dot}"></span>
            ${ok ? "Настроено" : item.optional ? "Необязательно" : "Нужна настройка .env"}
          </div>
          ${extra}
          ${probeBtn}
        </article>`;
    })
    .join("");

  grid.querySelectorAll(".probe-btn").forEach((btn) => {
    btn.addEventListener("click", () => runProbe(btn.dataset.probe));
  });

  $("#course-label").textContent = `${data.course_name} (${data.course_id})`;

  const tools = data.tools || {};
  const panel = $("#tools-panel");
  const groups = [
    ["Journal", tools.journal],
    ["Gitea", tools.gitea],
    ["Git", tools.git],
    ["Web", tools.web],
  ];
  panel.innerHTML = `
    <h2>Инструменты агента</h2>
    <div class="tool-chips">
      ${groups
        .map(
          ([name, g]) =>
            `<span class="chip"><strong>${name}</strong> ${g?.count ?? 0}</span>`
        )
        .join("")}
    </div>
    <details style="margin-top:0.6rem">
      <summary style="cursor:pointer;color:var(--muted);font-size:0.85rem">Показать имена</summary>
      <div class="tool-chips" style="margin-top:0.5rem">
        ${groups
          .flatMap(([, g]) => (g?.items || []).map((n) => `<span class="chip">${escapeHtml(n)}</span>`))
          .join("")}
      </div>
    </details>`;
}

async function fetchStatus() {
  const res = await fetch("/api/status");
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function runProbe(kind) {
  const path = kind === "journal" ? "/api/probe/journal" : "/api/probe/gitea";
  const btn = document.querySelector(`[data-probe="${kind}"]`);
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(path, { method: "POST" });
    const data = await res.json();
    const msg = data.ok
      ? `✓ ${kind}: OK (${data.count ?? data.login ?? ""})`
      : `✗ ${kind}: ${data.error || "ошибка"}`;
    appendLog({ ts: Date.now() / 1000, level: data.ok ? "info" : "error", message: msg });
  } finally {
    if (btn) btn.disabled = false;
  }
}

function addChatMessage(role, text) {
  const log = $("#chat-log");
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  wrap.innerHTML = `
    <div class="label">${role === "user" ? "Вы" : "Агент"}</div>
    <div class="bubble">${escapeHtml(text)}</div>`;
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

function setChatLoading(on) {
  const btn = $("#btn-send");
  btn.disabled = on;
  let typing = $("#typing-indicator");
  if (on && !typing) {
    typing = document.createElement("div");
    typing.id = "typing-indicator";
    typing.className = "typing";
    typing.textContent = "Агент думает…";
    $("#chat-log").appendChild(typing);
  } else if (!on && typing) {
    typing.remove();
  }
}

async function sendChat(message) {
  setChatLoading(true);
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, thread_id: threadId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    addChatMessage("agent", data.reply);
  } catch (err) {
    addChatMessage("agent", `Ошибка: ${err.message}`);
  } finally {
    setChatLoading(false);
  }
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const id = tab.dataset.tab;
      document.querySelectorAll(".tab-panel").forEach((p) => {
        p.hidden = p.id !== `panel-${id}`;
        p.classList.toggle("active", p.id === `panel-${id}`);
      });
    });
  });
}

function setupQuickPrompts() {
  const box = $("#quick-prompts");
  QUICK_PROMPTS.forEach((text) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text.length > 42 ? text.slice(0, 40) + "…" : text;
    b.title = text;
    b.addEventListener("click", () => {
      $("#chat-input").value = text;
      $("#chat-input").focus();
    });
    box.appendChild(b);
  });
}

function setupChat() {
  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const text = input.value.trim();
    if (!text) return;
    addChatMessage("user", text);
    input.value = "";
    sendChat(text);
  });
}

function renderPipelineJob(job) {
  const box = $("#pipeline-results");
  const status = $("#pipeline-status");
  status.textContent = job.message || job.status;

  if (!job.results?.length && !job.errors?.length) {
    if (job.status === "running") box.innerHTML = "<p class='typing'>Выполняется… смотрите журнал справа.</p>";
    return;
  }

  const cards = [
    ...(job.results || []).map(
      (r) => `
      <div class="result-card">
        <div class="task-id">${escapeHtml(r.task_id)}</div>
        <div>${escapeHtml(r.mode || "")} · ${escapeHtml(r.status || "")}</div>
        ${r.retries ? `<div>Повторов: ${r.retries}</div>` : ""}
      </div>`
    ),
    ...(job.errors || []).map(
      (e) => `<div class="result-card" style="border-color:var(--err)">${escapeHtml(e)}</div>`
    ),
  ];
  box.innerHTML = cards.join("");
}

async function startPipeline() {
  const btn = $("#btn-pipeline-start");
  btn.disabled = true;
  $("#pipeline-results").innerHTML = "";
  try {
    const res = await fetch("/api/pipeline/start", { method: "POST" });
    const { job_id } = await res.json();
    if (!res.ok) throw new Error("Не удалось запустить");
    pollPipeline(job_id);
  } catch (err) {
    $("#pipeline-status").textContent = err.message;
    btn.disabled = false;
  }
}

function pollPipeline(jobId) {
  if (pipelinePollTimer) clearInterval(pipelinePollTimer);
  pipelinePollTimer = setInterval(async () => {
    const res = await fetch(`/api/pipeline/${jobId}`);
    const job = await res.json();
    renderPipelineJob(job);
    if (job.status === "done" || job.status === "error") {
      clearInterval(pipelinePollTimer);
      $("#btn-pipeline-start").disabled = false;
    }
  }, 2500);
}

function connectLogStream() {
  if (logEventSource) logEventSource.close();
  logEventSource = new EventSource("/api/logs/stream");
  logEventSource.onmessage = (ev) => {
    try {
      appendLog(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
  };
}

function setupLog() {
  $("#btn-clear-log").addEventListener("click", () => {
    $("#log-stream").innerHTML = "";
  });
}

async function init() {
  setupTabs();
  setupQuickPrompts();
  setupChat();
  setupLog();
  $("#btn-pipeline-start").addEventListener("click", startPipeline);
  $("#btn-refresh-status").addEventListener("click", async () => {
    try {
      renderStatus(await fetchStatus());
      appendLog({ ts: Date.now() / 1000, level: "info", message: "Статус обновлён" });
    } catch (err) {
      appendLog({ ts: Date.now() / 1000, level: "error", message: String(err) });
    }
  });

  connectLogStream();

  try {
    const history = await fetch("/api/logs?limit=40");
    const data = await history.json();
    (data.entries || []).forEach(appendLog);
    renderStatus(await fetchStatus());
    appendLog({ ts: Date.now() / 1000, level: "info", message: "Панель готова" });
  } catch (err) {
    appendLog({ ts: Date.now() / 1000, level: "error", message: `Сервер: ${err.message}` });
  }
}

init();
