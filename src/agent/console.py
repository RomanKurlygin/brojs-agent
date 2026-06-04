"""Единый стиль сообщений в терминале."""

_TAG = "kfu-agent"


def log(msg: str) -> None:
    print(f"[{_TAG}] {msg}")


def log_detail(msg: str) -> None:
    print(f"         - {msg}")


def log_block(title: str) -> None:
    line = "-" * max(24, len(title) + 4)
    print(f"\n{line}\n  {title}\n{line}")
