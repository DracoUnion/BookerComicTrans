"""
LLM-based translation engine for Manga Translator.

Self-contained implementation (no external tool package dependency; the small
helpers ``render_prompt`` / ``ext_cont_block`` are inlined here).

Two translation paths are provided:

- :meth:`LLMTranslator.translate`  — translate a single text, with the
  translate -> review -> fix refinement loop (used for retranslating one
  region).
- :meth:`LLMTranslator.translate_many` — translate a whole batch at once.
  All the texts are merged into one JSON array (``TRANS_BATCH_PMT``); the
  model answers with a parallel JSON array, which is then split back per text.
  An optional batch-level review / fix pass is applied when ``rounds > 0``.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from manga_translator.core.translator import (
    TranslationEngine, TranslationResult,
)
from manga_translator.core.llm_client import (
    LLMClient, LLMConfigError, get_chat_model, parse_json_array,
    strip_code_fence, strip_content_block,
)
from manga_translator.core.llm_prompts import (
    TRANS_PMT, TRANS_CHK_PMT, TRANS_FIX_PMT,
    TRANS_BATCH_PMT, TRANS_BATCH_CHK_PMT, TRANS_BATCH_FIX_PMT,
)
from manga_translator.core.logger import get_logger

logger = get_logger("LLMTranslator")


# --------------------------------------------------------------------------
# Prompt rendering / parsing
# --------------------------------------------------------------------------

def render_prompt(prompt: str, **kw) -> str:
    """Substitute ``{name}`` placeholders with the given values."""
    return re.sub(r"{(\w+)}", lambda g: kw.get(g.group(1), g.group(0)), prompt)


def ext_cont_block(s: str) -> str:
    """Extract non-JSON output from its ``[content]...[/content]`` wrapper.

    Non-JSON outputs are expected to be wrapped in ``[content]...[/content]``
    (JSON outputs are wrapped in triple backticks instead, see ``parse_json``).
    As a defensive fallback a stray code fence is also stripped.
    """
    s = strip_content_block(s)
    s = strip_code_fence(s)
    return s


# --------------------------------------------------------------------------
# Language names for natural-language instructions
# --------------------------------------------------------------------------

LANG_NAMES = {
    "auto": "the source language（源语言）",
    "ja": "日语 (Japanese)",
    "jpn": "日语 (Japanese)",
    "zh": "中文 (Chinese)",
    "chi_sim": "简体中文 (Simplified Chinese)",
    "chi_tra": "繁体中文 (Traditional Chinese)",
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
    """Translation powered by an LLM, with optional review/fix passes."""

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

    # ------------------------------------------------------------------
    # Single-item translation (with per-item review / fix loop)
    # ------------------------------------------------------------------

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

    def _translate_with_review(self, client: LLMClient, text: str,
                               source_lang: str, target_lang: str) -> str:
        """translate -> (review -> fix)*, one text at a time."""
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

    # ------------------------------------------------------------------
    # Batch translation (all texts as one JSON array; JSON in / JSON out)
    # ------------------------------------------------------------------

    def translate_many(self, texts: List[str], source_lang: str = None,
                       target_lang: str = None) -> List[str]:
        """Translate a batch of texts in a single LLM round-trip.

        All texts are merged into one JSON array; the model returns a parallel
        JSON array; the results are split back and returned in the same order.
        Returns one string per input.
        """
        if not texts:
            return []

        source_lang = source_lang or self.source_lang or "auto"
        target_lang = target_lang or self.target_lang or "en"

        client = self._ensure_client()
        if client is None:
            return ["[LLM 未配置]"] * len(texts)

        try:
            results = self._batch_translate(
                client, texts, source_lang, target_lang)

            for _ in range(self.rounds):
                checks = self._batch_check(
                    client, texts, results, source_lang, target_lang)
                if not any(checks):
                    break
                results = self._batch_fix(
                    client, texts, results, checks,
                    source_lang, target_lang)

            return results
        except Exception as ex:
            logger.error(f"LLM batch translation failed: {ex}")
            return ["[翻译失败]" for _ in texts]

    def _batch_translate(self, client: LLMClient, texts: List[str],
                         source_lang: str, target_lang: str) -> List[str]:
        """One JSON-array translate call, with length alignment + retry."""
        src = LANG_NAMES.get(source_lang, source_lang)
        tgt = LANG_NAMES.get(target_lang, target_lang)
        texts_json = json.dumps(texts, ensure_ascii=False)
        prompt = (
            TRANS_BATCH_PMT
            .replace("{source_lang}", src)
            .replace("{target_lang}", tgt)
            .replace("{texts_json}", texts_json)
        )

        arr = parse_json_array(client.ask(prompt))
        if len(arr) != len(texts):
            # One retry for a length mismatch before settling.
            logger.debug("batch length mismatch, retrying")
            arr = parse_json_array(client.ask(prompt))
        return self._align(arr, texts)

    def _batch_check(self, client: LLMClient, texts: List[str],
                     translations: List[str], source_lang: str,
                     target_lang: str) -> List[Optional[str]]:
        """Review the whole batch at once; one problem string per item."""
        items = [{"src": s, "tgt": t} for s, t in zip(texts, translations)]
        items_json = json.dumps(items, ensure_ascii=False)
        prompt = TRANS_BATCH_CHK_PMT.replace("{items_json}", items_json)

        try:
            arr = parse_json_array(client.ask(prompt))
        except Exception:
            return []  # treat parse failure as "no problems"
        return self._collect_checks(arr, len(texts))

    def _batch_fix(self, client: LLMClient, texts: List[str],
                   translations: List[str], checks: List[Optional[str]],
                   source_lang: str, target_lang: str) -> List[str]:
        """Revise the whole batch at once from the review feedback."""
        items = [
            {"src": s, "tgt": t, "checks": c or ""}
            for s, t, c in zip(texts, translations, checks)
        ]
        items_json = json.dumps(items, ensure_ascii=False)
        prompt = TRANS_BATCH_FIX_PMT.replace("{items_json}", items_json)

        try:
            arr = parse_json_array(client.ask(prompt))
        except Exception:
            return translations  # keep current translations on failure
        return self._align(arr, texts)

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _align(arr: List, texts: List[str]) -> List[str]:
        """Align an answer array to the input length (truncate / pad)."""
        out = []
        for i in range(len(texts)):
            if i < len(arr) and isinstance(arr[i], str):
                out.append(arr[i])
            else:
                out.append("")
        return out

    @staticmethod
    def _collect_checks(arr: List, n: int) -> List[Optional[str]]:
        """Normalize a batch-check answer into one problem string per item."""
        checks = []
        for i in range(n):
            c = arr[i] if i < len(arr) else None
            if isinstance(c, str):
                checks.append(c if c.strip() else None)
            elif isinstance(c, list):
                parts = [str(x) for x in c if x]
                checks.append(" ".join(parts) if parts else None)
            else:
                checks.append(None)
        return checks

    @staticmethod
    def _augment(prompt: str, source_lang: str, target_lang: str) -> str:
        """Prepend an explicit language-direction instruction."""
        src = LANG_NAMES.get(source_lang, source_lang)
        tgt = LANG_NAMES.get(target_lang, target_lang)
        return (f"请将以下{src}内容翻译成{tgt}，并严格遵守下面的要求。\n\n"
                + prompt)

    @staticmethod
    def _clean(text: str) -> str:
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
