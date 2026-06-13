"""Пакетный пайплайн: все открытые задания курса."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from src.agent.graph.pipeline import pipeline

    state = {"tasks": [], "current_index": 0, "results": [], "errors": []}
    cfg = {"configurable": {"thread_id": "cli-pipeline-1"}}
    print("Пайплайн: старт…")
    out = await pipeline.ainvoke(state, cfg)
    print(f"Готово: {len(out['results'])} задание(й)")
    for r in out["results"]:
        print(f"  - {r.get('task_id')} ({r.get('mode')})")
    if out["errors"]:
        print("Сбои:")
        for e in out["errors"]:
            print(f"  ! {e}")


if __name__ == "__main__":
    asyncio.run(main())
