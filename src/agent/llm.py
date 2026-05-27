"""Единая инициализация LLM для всех агентов.

Цель: чтобы код работал и локально, и на автопроверке.

- Если задан OPENAI_API_KEY → используем OpenRouter.
- Иначе используем inference API журнала BroJS с JOURNAL_MCP_PAT/JOURNAL_TOKEN.
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

BROJS_INFERENCE_URL = "https://platform.brojs.ru/jrnl-bh/api/inference/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b:free"


def _api_key() -> str:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("JOURNAL_MCP_PAT")
        or os.getenv("JOURNAL_TOKEN")
        or ""
    )


def _base_url() -> str:
    if os.getenv("OPENAI_BASE_URL"):
        return os.environ["OPENAI_BASE_URL"]
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENROUTER_BASE_URL", OPENROUTER_URL)
    return BROJS_INFERENCE_URL


def _model() -> str:
    return os.getenv("OPENAI_MODEL") or os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL


llm = ChatOpenAI(
    model=_model(),
    base_url=_base_url(),
    api_key=_api_key(),
    temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
)
