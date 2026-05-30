import logging
import os
from functools import lru_cache

from langchain.chat_models import init_chat_model

from app.core.config import settings

logger = logging.getLogger(__name__)


def _sync_api_keys() -> None:
    """Push API keys from pydantic settings into os.environ so LangChain can find them."""
    if settings.GOOGLE_API_KEY:
        os.environ.setdefault("GOOGLE_API_KEY", settings.GOOGLE_API_KEY)
    if settings.ANTHROPIC_API_KEY:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY)
    if settings.OPENAI_API_KEY:
        os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    if settings.GROQ_API_KEY:
        os.environ.setdefault("GROQ_API_KEY", settings.GROQ_API_KEY)


@lru_cache(maxsize=8)
def get_llm(temperature: float = 0.0):
    _sync_api_keys()
    model = init_chat_model(
        model=settings.LLM_MODEL,
        model_provider=settings.LLM_PROVIDER,
        temperature=temperature,
    )
    logger.info(
        "Initialized LLM: provider=%s model=%s temperature=%s",
        settings.LLM_PROVIDER,
        settings.LLM_MODEL,
        temperature,
    )
    return model
