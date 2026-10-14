"""
LLM client for Manga Translator — self-contained.

The retry / request helpers below are self-contained and only require the
``openai`` SDK (no external tool package).

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
``OPENAI_USER_AGENT``   HTTP User-Agent header           ``MangaTranslator/1.0``
``OPENAI_TIMEOUT``      Read timeout in seconds          ``120``
``OPENAI_CONN_TIMEOUT`` Connect timeout in seconds       ``10``
======================  ===============================  ============

The module degrades gracefully: if the SDK is missing or no API key is set,
:class:`LLMClient` raises a clear :class:`LLMConfigError` when it is asked to
make a call, so the rest of the application keeps working with the non-LLM
engines.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import traceback
from typing import Any, Dict, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Instruction-token escaping
# --------------------------------------------------------------------------

INS_TOKEN_RE = re.compile(r"<\|([\w\-\.]+)\|>")


def ensure_utf8(text: str) -> str:
    """Keep only valid UTF-8 sequences."""
    return text.encode("utf8", "ignore").decode("utf8", "ignore")


def repl_ins_token(text: str) -> str:
    """Escape ``<|token|>`` so the model does not get confused by it."""
    return INS_TOKEN_RE.sub(r"</\1/>", text)


def repl_ins_token_msgs(msgs):
    """Escape instruction tokens inside a message list, in place."""
    for m in msgs:
        cont = m.get("content")
        if isinstance(cont, str):
            m["content"] = ensure_utf8(repl_ins_token(cont))
        elif isinstance(cont, list):
            for it in cont:
                if isinstance(it, dict) and it.get("type") == "text":
                    it["text"] = ensure_utf8(repl_ins_token(it["text"]))
    return msgs


def get_msgs_text(msgs) -> str:
    """Last user text inside a message list (for debug logging)."""
    for m in reversed(msgs):
        cont = m.get("content")
        if isinstance(cont, str):
            return cont
        elif isinstance(cont, list):
            for it in cont:
                if isinstance(it, dict) and it.get("type") == "text":
                    return it["text"]
    return ""


def json_dump_model(obj) -> str:
    """Serialize an object to a compact JSON string (safe for logs)."""
    return json.dumps(obj, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------
# Configuration (read from environment variables)
# --------------------------------------------------------------------------

class LLMConfigError(RuntimeError):
    """Raised when the LLM backend is misconfigured or unavailable."""


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def get_chat_model() -> str:
    """Text model: ``OPENAI_LANG_MODEL`` then ``OPENAI_CHAT_MODEL``."""
    return _env("OPENAI_LANG_MODEL") or _env("OPENAI_CHAT_MODEL", "gpt-3.5-turbo")


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


_CONFIG = {
    "api_key": _env("OPENAI_API_KEY"),
    "base_url": _env("OPENAI_BASE_URL"),
    "user_agent": _env("OPENAI_USER_AGENT", "MangaTranslator/1.0"),
    "read_timeout": _read_timeout(),
    "conn_timeout": _conn_timeout(),
    "repetition_regex": _env("OPENAI_REPETITION_REGEX", ""),
}


def _make_client():
    """Create an OpenAI client from the environment-driven config."""
    import openai  # lazy import so the rest of the app works without it

    if not _CONFIG["api_key"]:
        raise LLMConfigError(
            "未配置 OPENAI_API_KEY 环境变量，无法调用大模型。"
        )
    try:
        return openai.OpenAI(
            base_url=_CONFIG["base_url"] or None,
            api_key=_CONFIG["api_key"],
            default_headers={"User-Agent": _CONFIG["user_agent"]},
            timeout=openai.Timeout(
                read=_CONFIG["read_timeout"],
                connect=_CONFIG["conn_timeout"],
            ),
        )
    except Exception as ex:
        raise LLMConfigError(f"无法创建 OpenAI 客户端：{ex}")


def check_model_repetition(text: str):
    """Raise if the output matches the configured repetition regex."""
    rx = _CONFIG["repetition_regex"]
    if rx and re.search(rx, text):
        raise ValueError("检测到模型复读")


# --------------------------------------------------------------------------
# Low-level calls
# --------------------------------------------------------------------------

def call_llm(
    msgs,
    model_name,
    *,
    temp=None,
    top_p=None,
    frequency_penalty=None,
    presence_penalty=None,
    max_tokens=None,
    extra_body=None,
) -> str:
    """One chat completion call, returning the raw text answer."""
    if isinstance(msgs, str):
        msgs = [{"role": "user", "content": msgs}]
    msgs = repl_ins_token_msgs(msgs)
    logger.debug(f"ques: %s", json_dump_model(get_msgs_text(msgs))[:400])

    client = _make_client()
    res = client.chat.completions.create(
        messages=msgs,
        model=model_name,
        temperature=temp,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        max_tokens=max_tokens,
        extra_body=extra_body or None,
    )
    ans = (res.choices[0].message.content or "").strip()
    check_model_repetition(ans)
    if not ans:
        raise ValueError(f"回复为空：{res}")

    # Restore instruction-token form the model may have re-emitted.
    ans = re.sub(r"</([\w\-\.]+)/>", r"<|\1|>", ans)
    logger.debug(f"ans: %s", json_dump_model(ans)[:400])
    return ans


def call_llm_retry(
    msgs,
    model_name,
    *,
    retry=10,
    temp=None,
    top_p=None,
    frequency_penalty=None,
    presence_penalty=None,
    max_tokens=None,
    extra_body=None,
    parse_output=None,
):
    """Call with retry on transient errors (network, empty reply, etc.)."""
    for i in range(retry):
        try:
            res = call_llm(
                msgs, model_name,
                temp=temp,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                max_tokens=max_tokens,
                extra_body=extra_body,
            )
            return parse_output(res) if parse_output else res
        except KeyboardInterrupt:
            raise
        except Exception as ex:
            logger.debug(f"OpenAI retry {i + 1}: {ex}")
            logger.debug(traceback.format_exc())
            if i == retry - 1:
                raise ex


def ask_chatgpt_retry(
    ques,
    model_name,
    parse_output=None,
    **kwargs,
):
    """Text-only prompt with retry (``kwargs`` passed to call_llm_retry)."""
    return call_llm_retry(
        ques, model_name,
        parse_output=parse_output,
        **kwargs,
    )


def call_vlm_retry(
    img,
    ques,
    model_name,
    parse_output=None,
    **kwargs,
):
    """Vision prompt with retry: sends the image (PNG bytes) + question."""
    img_base64 = base64.b64encode(img).decode("ascii")
    msgs = [{
        "role": "user",
        "content": [
            {"type": "text", "text": ques},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_base64}"},
            },
        ],
    }]
    return call_llm_retry(
        msgs, model_name,
        parse_output=parse_output,
        **kwargs,
    )


# --------------------------------------------------------------------------
# JSON parsing helpers (tolerate code fences / slightly malformed output)
# --------------------------------------------------------------------------

def strip_code_fence(text: str) -> str:
    """Strip a surrounding ```(lang)\\n...\\n``` block if present."""
    m = re.search(r"```(?:\w+)?\s*[\r\n]*([\s\S]*?)[\r\n]*```", text)
    return m.group(1).strip() if m else text.strip()


def parse_json(text: str) -> Any:
    """Parse JSON, tolerating code fences and minor syntax errors."""
    text = strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import json_repair
            return json_repair.loads(text)
        except ImportError:  # pragma: no cover
            raise
        except Exception as ex:
            raise ValueError(f"无法解析 JSON：{ex}\n{text[:400]}")


def parse_json_array(text: str) -> List[Any]:
    """Parse a JSON array, allowing the model to wrap it in an object."""
    obj = parse_json(text)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        # Tolerate {"translations": [...]} / {"texts": [...]} / {"result": [...]}
        for v in obj.values():
            if isinstance(v, list):
                return v
    raise ValueError(f"未能解析出 JSON 数组：{text[:200]}")


# --------------------------------------------------------------------------
# Public facade
# --------------------------------------------------------------------------

class LLMClient:
    """Thin facade over the copied OpenAI helpers."""

    def __init__(self, model: str, *, temp: float = 1.0,
                 max_tokens: Optional[int] = None, retry: int = 10):
        if not is_configured():
            raise LLMConfigError(
                "未配置 OPENAI_API_KEY 环境变量，无法调用大模型。"
            )
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens
        self.retry = retry

    # -- text -------------------------------------------------------------

    def ask(
        self,
        prompt: str,
        parse_output=None,
        model: Optional[str] = None,
    ) -> str:
        """Send a text prompt and return the (optionally parsed) answer."""
        return ask_chatgpt_retry(
            prompt,
            model or self.model,
            parse_output=parse_output,
            retry=self.retry,
            temp=self.temp,
            max_tokens=self.max_tokens,
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
        return call_vlm_retry(
            img_png,
            prompt,
            model or self.model,
            parse_output=parse_output,
            retry=self.retry,
            temp=self.temp,
            max_tokens=self.max_tokens,
        )
