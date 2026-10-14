"""
LLM client for Manga Translator.

Wraps :mod:`BookerGptTool.openai` (the battle-tested retry / streaming /
tool-call helpers) behind a small, dependency-light facade so the OCR and
translation engines can call a vision or chat model without caring about the
transport details.

All connection settings are read from environment variables so nothing has to
be configured in the UI:

======================  ===============================  ============
Environment variable    Meaning                          Default
======================  ===============================  ============
``OPENAI_API_KEY``      API key (required)               ````
``OPENAI_BASE_URL``     API base URL                     ````
``OPENAI_CHAT_MODEL``   Text model                       ``gpt-3.5-turbo``
``OPENAI_VIS_MODEL``    Vision model (LLM OCR)           ````
``OPENAI_LANG_MODEL``   Text model override (optional)   <- ``OPENAI_CHAT_MODEL``
``OPENAI_USER_AGENT``   HTTP User-Agent header           ``claude-cli/2.1.41 (external, cli)``
``OPENAI_TIMEOUT``      Read timeout in seconds          ``120``
======================  ===============================  ============

The module degrades gracefully: if ``BookerGptTool`` is not installed, the
:class:`LLMClient` raises a clear :class:`LLMConfigError` when it is asked to
make a call, so the rest of the application keeps working with the non-LLM
engines.
"""

from __future__ import annotations

import os
from argparse import Namespace
from typing import Any, List, Optional

from manga_translator.core.logger import get_logger

logger = get_logger("LLMClient")


class LLMConfigError(RuntimeError):
    """Raised when the LLM backend is misconfigured or unavailable."""


# --------------------------------------------------------------------------
# Reuse BookerGptTool.openai
# --------------------------------------------------------------------------

def _import_booker():
    """Import the BookerGptTool LLM helpers, or return None if unavailable."""
    try:
        from BookerGptTool.openai import (
            call_vlm_retry,
            ask_chatgpt_retry,
            set_openai_props,
            logger as oai_logger,
        )
        import logging
        oai_logger.setLevel(logging.DEBUG)
        return call_vlm_retry, ask_chatgpt_retry, set_openai_props
    except Exception as ex:  # pragma: no cover - environment dependent
        logger.debug(f"BookerGptTool not available: {ex}")
        return None


_BOOKER = _import_booker()


# --------------------------------------------------------------------------
# Environment-driven configuration
# --------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def get_chat_model() -> str:
    """Text model: ``OPENAI_LANG_MODEL`` then ``OPENAI_CHAT_MODEL``."""
    return _env("OPENAI_LANG_MODEL") or \
        _env("OPENAI_CHAT_MODEL", "gpt-3.5-turbo")


def get_vision_model() -> str:
    """Vision model used for LLM OCR (``OPENAI_VIS_MODEL``)."""
    return _env("OPENAI_VIS_MODEL", "")


def is_configured() -> bool:
    """True when an API key is present (i.e. calls can be attempted)."""
    return bool(_env("OPENAI_API_KEY"))


def _read_timeout() -> int:
    try:
        return int(_env("OPENAI_TIMEOUT", "120"))
    except ValueError:
        return 120


def _conn_timeout() -> int:
    try:
        return int(_env("OPENAI_CONN_TIMEOUT", "10"))
    except ValueError:
        return 10


def build_args(
    model: str,
    *,
    retry: int = 10,
    temp: float = 1.0,
    max_tokens: Optional[int] = None,
) -> Namespace:
    """Build the ``argparse.Namespace`` that BookerGptTool helpers expect."""
    return Namespace(
        key=_env("OPENAI_API_KEY"),
        host=_env("OPENAI_BASE_URL"),
        model=model,
        vmodel=model,
        user_agent=_env("OPENAI_USER_AGENT",
                        "claude-cli/2.1.41 (external, cli)"),
        stream=True,
        read_timeout=_read_timeout(),
        conn_timeout=_conn_timeout(),
        repetition_regex="",
        no_think=False,
        retry=retry,
        temp=temp,
        top_p=None,
        frequency_penalty=None,
        presence_penalty=None,
        max_tokens=max_tokens,
        extra_body=None,
    )


class LLMClient:
    """Thin facade over the BookerGptTool OpenAI helpers."""

    def __init__(self, model: str, *, temp: float = 1.0,
                 max_tokens: Optional[int] = None, retry: int = 10):
        if _BOOKER is None:
            raise LLMConfigError(
                "BookerGptTool 未安装：请先 `pip install BookerGptTool` "
                "以启用大模型 OCR / 翻译。"
            )
        if not is_configured():
            raise LLMConfigError(
                "未配置 OPENAI_API_KEY 环境变量，无法调用大模型。"
            )

        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens
        self.args = build_args(model, retry=retry, temp=temp,
                               max_tokens=max_tokens)

        # Push key / url / UA / timeouts into the BookerGptTool openai module.
        _, _, set_openai_props = _BOOKER
        set_openai_props(self.args)

    # -- text -------------------------------------------------------------

    def ask(
        self,
        prompt: str,
        parse_output=None,
        model: Optional[str] = None,
    ) -> str:
        """Send a text prompt and return the (optionally parsed) answer."""
        _, ask_chatgpt_retry, _ = _BOOKER
        return ask_chatgpt_retry(
            prompt,
            model or self.model,
            self.args,
            parse_output=parse_output,
        )

    # -- vision -----------------------------------------------------------

    def ask_vlm(
        self,
        img_png: bytes,
        prompt: str,
        parse_output=None,
        model: Optional[str] = None,
    ) -> str:
        """Send an image + prompt to a vision model."""
        call_vlm_retry, _, _ = _BOOKER
        return call_vlm_retry(
            img_png,
            prompt,
            model or self.model,
            self.args,
            parse_output=parse_output,
        )
