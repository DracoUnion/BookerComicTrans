# -*- coding: utf-8 -*-
"""
Unit tests for the LLM output-format parsing logic.

Convention enforced across all LLM prompts:
  * JSON output  -> wrapped in triple backticks
  * non-JSON     -> wrapped in [content][/content]

The parsers must handle the expected wrapper, and also tolerate the other
wrapper being misused (defensive fallback).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from manga_translator.core.llm_client import (
    parse_json, parse_json_array, strip_code_fence, strip_content_block,
)
from manga_translator.core.llm_translator import (
    LLMTranslator, ext_cont_block, render_prompt,
)
from manga_translator.core.llm_prompts import (
    OCR_PMT, TRANS_PMT, TRANS_CHK_PMT, TRANS_FIX_PMT,
    TRANS_BATCH_PMT, TRANS_BATCH_CHK_PMT, TRANS_BATCH_FIX_PMT,
)


class TestParsing(unittest.TestCase):

    # ---- JSON output: triple backticks ----

    def test_ocr_fenced_json_object(self):
        out = '```json\n{"direction":"horizontal",' \
              '"contents":[{"type":"paragraph","markdown":"hi",' \
              '"bbox":[0.1,0.2,0.3,0.4]}]}\n```'
        d = parse_json(out)
        self.assertEqual(d["direction"], "horizontal")
        self.assertEqual(d["contents"][0]["markdown"], "hi")

    def test_batch_translate_fenced_array(self):
        out = '```\n["Hello","World","Test"]\n```'
        self.assertEqual(parse_json_array(out), ["Hello", "World", "Test"])

    def test_batch_check_fenced_array_with_null(self):
        out = '```json\n["", "生硬", null]\n```'
        self.assertEqual(parse_json_array(out), ["", "生硬", None])

    def test_batch_fix_fenced_array(self):
        out = '```\n["修正0","修正1"]\n```'
        self.assertEqual(parse_json_array(out), ["修正0", "修正1"])

    # ---- non-JSON output: [content] wrapper ----

    def test_trans_content_block(self):
        out = '[content]\n你好世界\n[/content]'
        self.assertEqual(ext_cont_block(out), "你好世界")

    def test_chk_perfect_content_block(self):
        out = '[content][PERFECT/][/content]'
        self.assertEqual(ext_cont_block(out), "[PERFECT/]")

    # ---- defensive tolerance ----

    def test_content_block_around_json(self):
        out = '[content]["a","b"][/content]'
        self.assertEqual(parse_json_array(out), ["a", "b"])

    def test_code_fence_around_prose(self):
        out = '```\nhello world\n```'
        self.assertEqual(ext_cont_block(out), "hello world")

    def test_unwrapped_prose(self):
        self.assertEqual(ext_cont_block("bar baz"), "bar baz")

    def test_strip_helpers(self):
        self.assertEqual(strip_code_fence("x ```py\na\n``` y"), "a")
        self.assertEqual(strip_content_block("[content]a[/content]b"), "a")


class TestBatchFlow(unittest.TestCase):
    """Exercise the full batch translate->check->fix loop with fenced JSON."""

    class _FakeClient:
        def __init__(self):
            self.calls = []

        def ask(self, prompt, parse_output=None, model=None):
            self.calls.append(prompt)
            if "重新翻译" in prompt:  # fix prompt (also mentions 审校意见)
                return '```\n["你好","世界(修正)","测试"]\n```'
            if "审校" in prompt:      # check prompt
                return '```json\n[null, ["生硬"], null]\n```'
            return '```\n["你好","世界","测试"]\n```'

    def test_full_loop(self):
        t = LLMTranslator("ja", "zh", rounds=1)
        t._client = self._FakeClient()
        texts = ["こんにちは", "世界", "テスト"]
        out = t.translate_many(texts, "ja", "zh")
        self.assertEqual(out, ["你好", "世界(修正)", "测试"])
        self.assertEqual(t._client.calls.__len__() if hasattr(t._client.calls, "__len__") else len(t._client.calls), 3)

    def test_prompt_requires_backticks(self):
        self.assertIn("三个反引号", TRANS_BATCH_PMT)
        self.assertIn("三个反引号", TRANS_BATCH_CHK_PMT)
        self.assertIn("三个反引号", TRANS_BATCH_FIX_PMT)
        self.assertNotIn("不要使用", TRANS_BATCH_PMT)


class TestPrompts(unittest.TestCase):
    """Confirm every prompt declares the expected output wrapper."""

    def test_json_prompts_require_backticks(self):
        json_prompts = {
            "OCR_PMT": OCR_PMT,
            "TRANS_BATCH_PMT": TRANS_BATCH_PMT,
            "TRANS_BATCH_CHK_PMT": TRANS_BATCH_CHK_PMT,
            "TRANS_BATCH_FIX_PMT": TRANS_BATCH_FIX_PMT,
        }
        for name, p in json_prompts.items():
            self.assertIn("```", p, f"{name} should require backticks")

    def test_text_prompts_require_content_block(self):
        text_prompts = {
            "TRANS_PMT": TRANS_PMT,
            "TRANS_CHK_PMT": TRANS_CHK_PMT,
            "TRANS_FIX_PMT": TRANS_FIX_PMT,
        }
        for name, p in text_prompts.items():
            self.assertIn("[content]", p, f"{name} should require [content]")

    def test_text_prompts_do_not_output_json(self):
        # A sanity check that these say JSON *input* but not JSON output.
        self.assertNotIn("只输出一个 JSON", TRANS_PMT)


if __name__ == "__main__":
    unittest.main(verbosity=2)