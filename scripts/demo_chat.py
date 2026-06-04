"""Интерактивный чат с оркестратором (agent)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from langchain_core.messages import HumanMessage


async def main() -> None:
    from src.agent.agent import agent

    print("brojs-agent — интерактивный режим (agent)")
    print("Команды: exit / quit / выход — завершить")
    print("Пример: «Какие субагенты у тебя есть?»\n")

    config = {"configurable": {"thread_id": "demo-chat-1"}}
    while True:
        try:
            user = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        if user.lower() in ("exit", "quit", "q", "выход"):
            break
        if not user:
            continue
        print("\nАгент думает...\n", flush=True)
        try:
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=user)]},
                config,
            )
            print("Агент:", result["messages"][-1].content, "\n", flush=True)
        except Exception as exc:
            print(f"Ошибка: {exc}\n", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
