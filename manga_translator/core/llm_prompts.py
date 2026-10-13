"""
LLM prompts for Manga Translator.

The heavy lifting is delegated to the prompts shipped with ``BookerGptTool``,
which are reused verbatim for consistency with the rest of the tool chain:

- ``OCR_PMT``        -> vision OCR (JSON of typed blocks with relative bboxes)
- ``TRANS_PMT``      -> initial translation
- ``TRANS_CHK_PMT``  -> translation review / critique
- ``TRANS_FIX_PMT``  -> revised translation incorporating the critique

If ``BookerGptTool`` is not importable, self-contained fallbacks are used so
the module can still be imported (the LLM engines will simply fail later with
a clear configuration error).
"""

from __future__ import annotations

from manga_translator.core.logger import get_logger

logger = get_logger("LLMPrompts")


# --------------------------------------------------------------------------
# Reuse BookerGptTool prompts where possible
# --------------------------------------------------------------------------

def _import_prompts():
    try:
        from BookerGptTool.pdf_ocr_pmt import OCR_PMT
        from BookerGptTool.trans_chunk_pmt import (
            TRANS_PMT, TRANS_CHK_PMT, TRANS_FIX_PMT,
        )
        return OCR_PMT, TRANS_PMT, TRANS_CHK_PMT, TRANS_FIX_PMT
    except Exception as ex:  # pragma: no cover - environment dependent
        logger.debug(f"BookerGptTool prompts unavailable: {ex}")
        return None

_PROMPTS = _import_prompts()


# --------------------------------------------------------------------------
# Fallbacks (only used when BookerGptTool is missing)
# --------------------------------------------------------------------------

_FALLBACK_OCR_PMT = '''
你是一个专业的文档编辑助手。请查看给定图片，提取出其中的所有标题、段落、列表、表格、插图、引用、代码块等，并一定要忽略页眉和页脚，以给定 JSON 格式输出。注意只需要输出 JSON，不需要输出其它任何东西。

## 注意

1.  BBOX 应该用相对坐标，即整个图片的一个比例，不要使用像素单位的绝对坐标！
2.  如果图片不包含任何文字或模糊无法识别，请返回`contents`为空，`direction`为`"horizontal"`的 JSON。
3.  JSON 应包含在三个反引号（```）中返回。

## 格式

```
{
\t"direction": "horizontal|vertical",
\t"contents": [
\t\t{
\t\t\t"type": "paragraph|title|list|table|quote|image|code|header|footer",
\t\t\t"markdown": "in markdown format",
\t\t\t"bbox": [0.xmin, 0.ymin, 0.xmax, 0.ymax]
\t\t},
\t\t...
\t]
}
```
'''

_FALLBACK_TRANS_PMT = '''
你是一位精通简体中文的专业翻译，尤其擅长将漫画/日语原文翻译成浅显易懂的中文。请你帮我将给定原文翻译成中文，风格与中文科普读物相似。

## 翻译规则

+   翻译时要准确传达原文的事实和背景。
+   即使上意译也要保留原始段落格式，以及保留术语。
+   人名不翻译
+   对于 Figure 和 Table，翻译的同时保留原有格式。
+   输入格式为 Markdown 格式，输出格式也必须保留原始 Markdown 格式

## 注意事项

+   保持原有格式，不要遗漏任何信息
+   译文需要包含在“[content]...[/content]”中。

## 原文

[content]
{en}
[/content]
'''

_FALLBACK_TRANS_CHK_PMT = '''
你是一位精通简体中文的专业翻译。请你根据给定原文和译文，指出其中存在的具体问题，要准确描述：

1.  不符合中文表达习惯，明确指出不符合的地方
2.  语句不通顺，指出位置，不需要给出修改意见
3.  晦涩难懂，不易理解

## 注意事项

+   问题以列表形式输出，包含在“[content]...[/content]”中。
+   如果没有任何问题，请输出“[PERFECT/]”。

## 原文

[content]
{en}
[/content]

## 译文

[content]
{zh}
[/content]
'''

_FALLBACK_TRANS_FIX_PMT = '''
你是一位精通简体中文的专业翻译。请你根据给定原文、译文和审核意见，重新进行翻译，保证内容的原意的基础上，使其更易于理解，更符合中文的表达习惯，同时保持原有的格式不变。

## 注意事项

+   保持原有格式，不要遗漏任何信息
+   译文需要包含在“[content]...[/content]”中。

## 原文

[content]
{en}
[/content]

## 译文

[content]
{zh}
[/content]

## 审核意见

[content]
{checks}
[/content]
'''


if _PROMPTS is not None:
    OCR_PMT, TRANS_PMT, TRANS_CHK_PMT, TRANS_FIX_PMT = _PROMPTS
    PROMPTS_SOURCE = "BookerGptTool"
else:  # pragma: no cover
    OCR_PMT = _FALLBACK_OCR_PMT
    TRANS_PMT = _FALLBACK_TRANS_PMT
    TRANS_CHK_PMT = _FALLBACK_TRANS_CHK_PMT
    TRANS_FIX_PMT = _FALLBACK_TRANS_FIX_PMT
    PROMPTS_SOURCE = "fallback"


__all__ = [
    "OCR_PMT",
    "TRANS_PMT",
    "TRANS_CHK_PMT",
    "TRANS_FIX_PMT",
    "PROMPTS_SOURCE",
]
