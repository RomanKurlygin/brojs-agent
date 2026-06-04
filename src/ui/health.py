"""Проверка окружения и подключений для UI."""
from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

from src.agent.constants import GITEA_BASE_URL, GITEA_OWNER
from src.agent.gitea_tools import GITEA_TOOLS
from src.agent.mcp_client import JOURNAL_COURSES_LESSONS, JOURNAL_TASKS_SUBMISSIONS, JOURNAL_PREFIX, _fetch_tools
from src.agent.tools import GIT_TOOLS, WEB_TOOLS

load_dotenv()

_PLACEHOLDERS = {
    "YOUR_OPENROUTER_KEY_HERE",
    "YOUR_JOURNAL_TOKEN_HERE",
    "YOUR_GITEA_TOKEN_HERE",
    "YOUR_GITEA_USERNAME_HERE",
    "",
}


def _configured(value: str | None) -> bool:
    v = (value or "").strip()
    return bool(v) and v not in _PLACEHOLDERS


def env_status() -> dict[str, Any]:
    keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "JOURNAL_TOKEN": os.getenv("JOURNAL_TOKEN"),
        "GITEA_TOKEN": os.getenv("GITEA_TOKEN"),
        "GITEA_OWNER": os.getenv("GITEA_OWNER"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
    }
    model = os.getenv("OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL") or "openai/gpt-oss-20b:free"
    return {
        "llm": {
            "ok": _configured(keys["OPENAI_API_KEY"]),
            "model": model,
            "label": "OpenRouter / LLM",
        },
        "journal": {
            "ok": _configured(keys["JOURNAL_TOKEN"]),
            "label": "BroJS Journal",
        },
        "gitea": {
            "ok": _configured(keys["GITEA_TOKEN"]) and _configured(keys["GITEA_OWNER"]),
            "owner": GITEA_OWNER or "—",
            "label": "Gitea",
        },
        "tavily": {
            "ok": _configured(keys["TAVILY_API_KEY"]),
            "optional": True,
            "label": "Веб-поиск (Tavily)",
        },
    }


def tool_inventory() -> dict[str, Any]:
    journal_count = len(JOURNAL_COURSES_LESSONS) + len(JOURNAL_TASKS_SUBMISSIONS)
    return {
        "journal": {
            "count": journal_count,
            "items": sorted(JOURNAL_COURSES_LESSONS | JOURNAL_TASKS_SUBMISSIONS),
            "prefix": JOURNAL_PREFIX,
        },
        "gitea": {"count": len(GITEA_TOOLS), "items": [t.name for t in GITEA_TOOLS]},
        "git": {"count": len(GIT_TOOLS), "items": [t.name for t in GIT_TOOLS]},
        "web": {"count": len(WEB_TOOLS), "items": [t.name for t in WEB_TOOLS]},
    }


async def probe_journal() -> dict[str, Any]:
    if not _configured(os.getenv("JOURNAL_TOKEN")):
        return {"ok": False, "error": "JOURNAL_TOKEN не задан"}
    try:
        tools_by_server = await _fetch_tools()
        tools = tools_by_server.get("journal-bh-professor", [])
        names = [t.name.removeprefix(JOURNAL_PREFIX) for t in tools if t.name.startswith(JOURNAL_PREFIX)]
        return {"ok": len(tools) > 0, "count": len(tools), "tools": sorted(names)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def probe_gitea() -> dict[str, Any]:
    token = os.getenv("GITEA_TOKEN", "")
    if not _configured(token):
        return {"ok": False, "error": "GITEA_TOKEN не задан"}
    try:
        resp = httpx.get(
            f"{GITEA_BASE_URL}/api/v1/user",
            headers={"Authorization": f"token {token}"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        user = resp.json()
        login = user.get("login", "")
        return {"ok": True, "login": login, "owner_match": login == GITEA_OWNER}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
