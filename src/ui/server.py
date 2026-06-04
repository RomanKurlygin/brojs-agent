"""Веб-интерфейс brojs-agent: статус, чат, пайплайн."""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agent.constants import COURSE_ID
from src.ui import health
from src.ui.activity import PipelineJob, _jobs, activity

ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = ROOT / "ui" / "static"

load_dotenv(ROOT / ".env")

app = FastAPI(title="brojs-agent UI", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str = "ui-chat-1"


class ChatResponse(BaseModel):
    reply: str
    thread_id: str


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    return {
        "course_id": COURSE_ID,
        "course_name": "KFU-26-1",
        "env": health.env_status(),
        "tools": health.tool_inventory(),
    }


@app.post("/api/probe/journal")
async def api_probe_journal() -> dict[str, Any]:
    activity.activity.emit("info", "Проверка Journal MCP…")
    result = await health.probe_journal()
    level = "info" if result.get("ok") else "error"
    activity.activity.emit(level, f"Journal: {result}")
    return result


@app.post("/api/probe/gitea")
async def api_probe_gitea() -> dict[str, Any]:
    activity.activity.emit("info", "Проверка Gitea…")
    result = await health.probe_gitea()
    level = "info" if result.get("ok") else "error"
    activity.activity.emit(level, f"Gitea: {result}")
    return result


@app.get("/api/logs")
async def api_logs(limit: int = 120) -> dict[str, Any]:
    return {"entries": activity.activity.history(limit=limit)}


@app.get("/api/logs/stream")
async def api_logs_stream() -> StreamingResponse:
    async def event_generator():
        queue = await activity.activity.subscribe()
        try:
            for entry in activity.activity.history(30):
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
            while True:
                entry = await queue.get()
                payload = entry.to_dict()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            activity.activity.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(body: ChatRequest) -> ChatResponse:
    from langchain_core.messages import HumanMessage

    from src.agent.agent import agent

    activity.activity.emit("info", f"Чат: {body.message[:80]}…")
    try:
        with activity.activity.capture_console():
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=body.message)]},
                {"configurable": {"thread_id": body.thread_id}},
            )
        last = result["messages"][-1]
        reply = getattr(last, "content", str(last))
        activity.activity.emit("info", "Ответ агента получен")
        return ChatResponse(reply=reply, thread_id=body.thread_id)
    except Exception as exc:
        activity.activity.emit("error", f"Чат: {exc}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _run_pipeline_job(job_id: str) -> None:
    from src.agent.graph.pipeline import pipeline

    job = _jobs[job_id]
    job.status = "running"
    job.message = "Загрузка заданий из журнала…"

    state: dict[str, Any] = {
        "tasks": [],
        "current_index": 0,
        "results": [],
        "errors": [],
    }
    cfg = {"configurable": {"thread_id": f"ui-pipeline-{job_id}"}}

    try:
        with activity.activity.capture_console():
            activity.activity.emit("info", "Пайплайн: старт")
            out = await pipeline.ainvoke(state, cfg)
            job.results = list(out.get("results", []))
            job.errors = list(out.get("errors", []))
            job.tasks_total = len(out.get("tasks", [])) or len(job.results) + len(job.errors)
            job.tasks_done = len(job.results)
            job.status = "done"
            job.message = f"Готово: {len(job.results)} успешно"
            if job.errors:
                job.message += f", сбоев: {len(job.errors)}"
            activity.activity.emit("info", job.message)
    except Exception as exc:
        job.status = "error"
        job.message = str(exc)
        job.errors.append(str(exc))
        activity.activity.emit("error", f"Пайплайн: {exc}")


@app.post("/api/pipeline/start")
async def api_pipeline_start() -> dict[str, str]:
    running = [j for j in _jobs.values() if j.status == "running"]
    if running:
        raise HTTPException(status_code=409, detail="Пайплайн уже выполняется")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = PipelineJob(id=job_id)
    asyncio.create_task(_run_pipeline_job(job_id))
    activity.activity.emit("info", f"Пайплайн запущен (job {job_id})")
    return {"job_id": job_id}


@app.get("/api/pipeline/{job_id}")
async def api_pipeline_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {
        "id": job.id,
        "status": job.status,
        "message": job.message,
        "tasks_total": job.tasks_total,
        "tasks_done": job.tasks_done,
        "results": job.results,
        "errors": job.errors,
    }


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
