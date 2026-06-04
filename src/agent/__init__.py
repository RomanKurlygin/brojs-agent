"""Пакет агента (ленивая загрузка — не тянет MCP при import src.agent)."""

__all__ = ["agent", "homework_direct_agent", "rework_agent"]


def __getattr__(name: str):
    if name in __all__:
        from src.agent.agent import agent, homework_direct_agent, rework_agent

        return {
            "agent": agent,
            "homework_direct_agent": homework_direct_agent,
            "rework_agent": rework_agent,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
