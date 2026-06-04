"""Журнал событий для веб-UI (буфер + подписчики SSE)."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

_BUFFER_MAX = 400


@dataclass
class LogEntry:
    ts: float
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts, "level": self.level, "message": self.message}


class ActivityLog:
    def __init__(self) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=_BUFFER_MAX)
        self._subscribers: set[asyncio.Queue[LogEntry]] = set()
        self._lock = asyncio.Lock()

    def emit(self, level: str, message: str) -> None:
        entry = LogEntry(ts=time.time(), level=level, message=message)
        self._entries.append(entry)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    def history(self, limit: int = 120) -> list[dict[str, Any]]:
        items = list(self._entries)[-limit:]
        return [e.to_dict() for e in items]

    async def subscribe(self) -> asyncio.Queue[LogEntry]:
        queue: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=200)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[LogEntry]) -> None:
        self._subscribers.discard(queue)

    @contextmanager
    def capture_console(self) -> Iterator[None]:
        """Дублирует вывод console.log в журнал UI."""
        import src.agent.console as console

        orig_log = console.log
        orig_detail = console.log_detail
        orig_block = console.log_block

        def log(msg: str) -> None:
            self.emit("info", msg)
            orig_log(msg)

        def log_detail(msg: str) -> None:
            self.emit("detail", msg)
            orig_detail(msg)

        def log_block(title: str) -> None:
            self.emit("block", title)
            orig_block(title)

        console.log = log  # type: ignore[method-assign]
        console.log_detail = log_detail  # type: ignore[method-assign]
        console.log_block = log_block  # type: ignore[method-assign]
        try:
            yield
        finally:
            console.log = orig_log  # type: ignore[method-assign]
            console.log_detail = orig_detail  # type: ignore[method-assign]
            console.log_block = orig_block  # type: ignore[method-assign]


activity = ActivityLog()


@dataclass
class PipelineJob:
    id: str
    status: str = "pending"  # pending | running | done | error
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    tasks_total: int = 0
    tasks_done: int = 0
    message: str = ""

_jobs: dict[str, PipelineJob] = {}
