"""
LLM-based translation engine for Manga Translator.

Implements the translate -> review -> fix refinement loop used by
``BookerGptTool.trans_chunk`` (see ``tr_trans_group``), reusing the shared
prompts:

- ``TRANS_PMT``      initial translation
- ``TRANS_CHK_PMT``  critique of the translation
- ``TRANS_FIX_PMT``  revised translation incorporating the critique

The loop stops as soon as the reviewer returns ``[PERFECT/]`` or after
``rounds`` iterations.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from manga_translator.core.translator import (
    TranslationEngine, TranslationResult,
)
from manga_translator.core.llm_client import (
    LLMClient, LLMConfigError, get_chat_model,
)
from manga_translator.core.llm_prompts import (
    TRANS_PMT, TRANS_CHK_PMT, TRANS_FIX_PMT,
)
from manga_translator.core.logger import get_logger

logger = get_logger("LLMTranslator")


# --------------------------------------------------------------------------
# Prompt rendering / parsing (reuse BookerGptTool.util when available)
# --------------------------------------------------------------------------

try:
    from BookerGptTool.util import render_prompt, ext_cont_block
    _HAS_UTIL = True
except Exception:  # pragma: no cover
    _HAS_UTIL = False

    def render_prompt(prompt: str, **kw) -> str:
        return re.sub(r"{(\w+)}", lambda g: kw.get(g.group(1), g.group(0)), prompt)

    def ext_cont_block(s: str) -> str:
        m = re.search(r"\[content\]([\s\S]+?)\[/content\]", s)
        return m.group(1) if m else s


# --------------------------------------------------------------------------
# Language names for natural-language instructions
# --------------------------------------------------------------------------

LANG_NAMES = {
    "auto": "the source language",
    "ja": "日语 (Japanese)",
    "jpn": "日语 (Japanese)",
    "zh": "中文 (Chinese)",
    "chi_sim": "简体中文 (Simplified Chinese)",
    "en": "英语 (English)",
    "eng": "英语 (English)",
    "ko": "韩语 (Korean)",
    "kor": "韩语 (Korean)",
    "fr": "法语 (French)",
    "de": "德语 (German)",
    "es": "西班牙语 (Spanish)",
    "ru": "俄语 (Russian)",
}


class LLMTranslator(TranslationEngine):
    """Translation powered by an LLM, with an optional review/fix loop."""

    def __init__(self, source_lang: Optional[str] = None,
                 target_lang: Optional[str] = None,
                 rounds: int = 1,
                 model: Optional[str] = None):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.rounds = max(0, int(rounds))
        self.model = model or get_chat_model()
        self._client: Optional[LLMClient] = None
        self._init_failed = False

    # -- lazy -------------------------------------------------------------

    def _ensure_client(self) -> Optional[LLMClient]:
        if self._client is not None or self._init_failed:
            return self._client
        try:
            self._client = LLMClient(self.model, temp=0.3, retry=5)
        except LLMConfigError as ex:
            logger.warning(f"LLM translation unavailable: {ex}")
            self._init_failed = True
        return self._client

    # -- interface --------------------------------------------------------

    @property
    def name(self) -> str:
        return "LLM"

    @property
    def is_available(self) -> bool:
        from manga_translator.core.llm_client import is_configured
        return is_configured()

    def get_supported_languages(self) -> Dict[str, str]:
        return {
            "auto": "Auto Detect",
            "ja": "Japanese",
            "zh": "Chinese",
            "ko": "Korean",
            "en": "English",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "ru": "Russian",
        }

    def translate(self, text: str, source_lang: str = None,
                  target_lang: str = None) -> TranslationResult:
        source_lang = source_lang or self.source_lang or "auto"
        target_lang = target_lang or self.target_lang or "en"

        if not text.strip():
            return self._result(text, "", source_lang, target_lang, 1.0)

        client = self._ensure_client()
        if client is None:
            return self._result(
                text, "[LLM 未配置]", source_lang, target_lang, 0.0)

        try:
            translated = self._translate_with_review(
                client, text, source_lang, target_lang)
            return self._result(
                text, translated, source_lang, target_lang, 0.95)
        except Exception as ex:
            logger.error(f"LLM translation failed: {ex}")
            return self._result(
                text, f"[翻译失败: {ex}]", source_lang, target_lang, 0.0)

    # -- refinement loop --------------------------------------------------

    def _translate_with_review(self, client: LLMClient, text: str,
                               source_lang: str, target_lang: str) -> str:
        """translate -> (review -> fix)*, mirroring BookerGptTool."""
        prompt = self._augment(TRANS_PMT, source_lang, target_lang)
        ques = render_prompt(prompt, en=text)
        trans = self._clean(client.ask(ques, parse_output=ext_cont_block))

        for _ in range(self.rounds):
            chk_ques = render_prompt(
                self._augment(TRANS_CHK_PMT, source_lang, target_lang),
                en=text, zh=trans,
            )
            checks = client.ask(chk_ques, parse_output=ext_cont_block).strip()
            if "[PERFECT/]" in checks or not checks:
                break
            fix_ques = render_prompt(
                self._augment(TRANS_FIX_PMT, source_lang, target_lang),
                en=text, zh=trans, checks=checks,
            )
            trans = self._clean(
                client.ask(fix_ques, parse_output=ext_cont_block))

        return trans

    @staticmethod
    def _augment(prompt: str, source_lang: str, target_lang: str) -> str:
        """Add a language-direction line tailored to the request.

        The shared prompts are written for ->Chinese; when the target differs,
        a short explicit instruction is prepended so the model follows it.
        """
        src = LANG_NAMES.get(source_lang, source_lang)
        tgt = LANG_NAMES.get(target_lang, target_lang)
        direction = f"请将以下{src}内容翻译成{tgt}，并严格遵守下面的要求。\n\n"
        return direction + prompt

    @staticmethod
    def _clean(text: str) -> str:
        """Strip stray content markers the model may re-emit."""
        return (text or "").strip()

    @staticmethod
    def _result(src: str, dst: str, source_lang: str, target_lang: str,
                confidence: float) -> TranslationResult:
        return TranslationResult(
            source_text=src,
            translated_text=dst,
            source_language=source_lang,
            target_language=target_lang,
            engine="LLM",
            confidence=confidence,
        )
