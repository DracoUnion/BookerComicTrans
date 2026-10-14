"""
LLM prompts for Manga Translator.

All prompt templates are self-contained in this module — there is no runtime
dependency on any external tool package.

- ``OCR_PMT``        -> vision OCR (JSON of typed blocks with relative bboxes)
- ``TRANS_PMT``      -> single-item translation
- ``TRANS_CHK_PMT``  -> single-item translation review
- ``TRANS_FIX_PMT``  -> single-item revised translation
- ``TRANS_BATCH_PMT``-> batch translation: all texts merged into one JSON
                        array; the model answers with a parallel JSON array,
                        which is split back per text afterwards.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# OCR (vision model, structured JSON output)
# --------------------------------------------------------------------------

OCR_PMT = '''
你是一个专业的文档编辑助手。请查看给定图片，提取出其中的所有标题、段落、列表、表格、插图、引用、代码块等，并一定要忽略页眉和页脚，以给定 JSON  格式输出。注意只需要输出 JSON，不需要输出其它任何东西。

## 注意

1.  BBOX 应该用相对坐标，即整个图片的一个比例，不要使用像素单位的绝对坐标！
2.  如果图片不包含任何文字或模糊无法识别，请返回`contents`为空，`direction`为`"horizontal"`的 JSON。
3.  JSON 应包含在三个反引号（```）中返回。

## 格式

```
{
	"direction": "horizontal|vertical",
	"contents": [
		{
			"type": "paragraph|title|list|table|quote|image|code|header|footer",
			"markdown": "in markdown format",
			"bbox": [0.xmin, 0.ymin, 0.xmax, 0.ymax]
		},
		...
	]
}
```
'''

# --------------------------------------------------------------------------
# Single-item translation
# --------------------------------------------------------------------------

TRANS_PMT = '''
你是一位精通简体中文的专业翻译，尤其擅长将专业学术论文翻译成浅显易懂的科普文章。请你帮我将给定英文原文翻译成中文，风格与中文科普读物相似。

## 翻译规则

+   翻译时要准确传达原文的事实和背景。
+   即使上意译也要保留原始段落格式，以及保留术语，例如 FLAC，JPEG 等。保留公司缩写，例如 Microsoft, Amazon, OpenAI 等。
+   人名不翻译
+   同时要保留引用的论文，例如 [20] 这样的引用。
+   对于 Figure 和 Table，翻译的同时保留原有格式，例如：“Figure 1: ”翻译为“图 1: ”，“Table 1: ”翻译为：“表 1: ”。
+   全角括号换成半角括号，并在左括号前面加半角空格，右括号后面加半角空格。
+   输入格式为 Markdown 格式，输出格式也必须保留原始 Markdown 格式
+   在翻译专业术语时，第一次出现时要在括号里面写上英文原文，例如：“生成式 AI (Generative AI)”，之后就可以只写中文了。
+   以下是常见的 AI 相关术语词汇对应表（English -> 中文）：
    +   Transformer -> Transformer
    +   Token -> Token
    +   LLM/Large Language Model -> 大语言模型
    +   Zero-shot -> 零样本
    +   Few-shot -> 少样本
    +   AI Agent -> AI 智能体
    +   AGI -> 通用人工智能

## 注意事项

+   保持原有格式，不要遗漏任何信息
+   译文需要包含在“[content]...[/content]”中。

## 原文

[content]
{en}
[/content]
'''

# --------------------------------------------------------------------------
# Single-item translation review (TRANS_CHK_PMT)
# --------------------------------------------------------------------------

TRANS_CHK_PMT = '''
你是一位精通简体中文的专业翻译，尤其擅长将专业学术论文翻译成浅显易懂的科普文章。请你根据给定原文和译文，指出其中存在的具体问题，要准确描述，不宜笼统的表示，也不需要增加原文不存在的内容或格式，包括不仅限于：

1.  不符合中文表达习惯，明确指出不符合的地方
2.  语句不通顺，指出位置，不需要给出修改意见
3.  晦涩难懂，不易理解，可以尝试给出解释

## 翻译规则

+   翻译时要准确传达原文的事实和背景。
+   即使上意译也要保留原始段落格式，以及保留术语，例如 FLAC，JPEG 等。保留公司缩写，例如 Microsoft, Amazon, OpenAI 等。
+   人名不翻译
+   同时要保留引用的论文，例如 [20] 这样的引用。
+   对于 Figure 和 Table，翻译的同时保留原有格式，例如：“Figure 1: ”翻译为“图 1: ”，“Table 1: ”翻译为：“表 1: ”。
+   全角括号换成半角括号，并在左括号前面加半角空格，右括号后面加半角空格。
+   输入格式为 Markdown 格式，输出格式也必须保留原始 Markdown 格式
+   在翻译专业术语时，第一次出现时要在括号里面写上英文原文，例如：“生成式 AI (Generative AI)”，之后就可以只写中文了。
+   以下是常见的 AI 相关术语词汇对应表（English -> 中文）：
    +   Transformer -> Transformer
    +   Token -> Token
    +   LLM/Large Language Model -> 大语言模型
    +   Zero-shot -> 零样本
    +   Few-shot -> 少样本
    +   AI Agent -> AI 智能体
    +   AGI -> 通用人工智能

## 注意事项

+   问题以列表形式输出，包含在“[content]...[/content]”中。
+   如果没有任何问题，请输出“[PERFECT/]”。

## 输出格式

[content]
1.  {问题1}
2.  {问题2}
3.  {问题3}
4.  ...
[/content]

## 原文

[content]
{en}
[/content]

## 译文

[content]
{zh}
[/content]
'''

# --------------------------------------------------------------------------
# Single-item revised translation (TRANS_FIX_PMT)
# --------------------------------------------------------------------------

TRANS_FIX_PMT = '''
你是一位精通简体中文的专业翻译，尤其擅长将专业学术论文翻译成浅显易懂的科普文章。请你根据给定原文、译文和审核意见，重新进行翻译，保证内容的原意的基础上，使其更易于理解，更符合中文的表达习惯，同时保持原有的格式不变。


## 翻译规则

+   翻译时要准确传达原文的事实和背景。
+   即使上意译也要保留原始段落格式，以及保留术语，例如 FLAC，JPEG 等。保留公司缩写，例如 Microsoft, Amazon, OpenAI 等。
+   人名不翻译
+   同时要保留引用的论文，例如 [20] 这样的引用。
+   对于 Figure 和 Table，翻译的同时保留原有格式，例如：“Figure 1: ”翻译为“图 1: ”，“Table 1: ”翻译为：“表 1: ”。
+   全角括号换成半角括号，并在左括号前面加半角空格，右括号后面加半角空格。
+   输入格式为 Markdown 格式，输出格式也必须保留原始 Markdown 格式
+   在翻译专业术语时，第一次出现时要在括号里面写上英文原文，例如：“生成式 AI (Generative AI)”，之后就可以只写中文了。
+   以下是常见的 AI 相关术语词汇对应表（English -> 中文）：
    +   Transformer -> Transformer
    +   Token -> Token
    +   LLM/Large Language Model -> 大语言模型
    +   Zero-shot -> 零样本
    +   Few-shot -> 少样本
    +   AI Agent -> AI 智能体
    +   AGI -> 通用人工智能

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

# --------------------------------------------------------------------------
# Batch translation (all texts as one JSON array, JSON in / JSON out)
# --------------------------------------------------------------------------

TRANS_BATCH_PMT = '''
你是一位专业翻译。请将下面 JSON 数组中列出的每一条文本都翻译成{target_lang}，源语言为{source_lang}。

## 翻译规则

+   翻译时要准确传达原文的意思和背景，不要增删内容。
+   保留原有格式和标记（如列表前缀、编号、``代码``、表格符号等），代码内容本身不翻译。
+   专有名词和术语（FLAC、JPEG、Microsoft、Amazon、OpenAI 等）不翻译，人名不翻译，引用编号（如 [20]）保留。
+   Figure、Table 翻译内容但保留前缀格式。
+   如果某条原文为空字符串，对应的译文也必须是空字符串 ""。
+   如果某条无法翻译，原样返回该条原文。

## 要翻译的文本（JSON 数组，元素顺序即编号 0,1,2,...）

{texts_json}

## 输出要求

+   只输出一个 JSON 数组，不要包含任何其它文字，不要使用 ``` 代码块包裹。
+   输出数组的长度必须与输入完全一致，顺序一一对应。
+   每个元素是对应位置的译文（字符串）。
+   格式示例：["译文0", "译文1", "译文2"]
'''

# --------------------------------------------------------------------------
# Batch review / fix (optional refinement pass over the whole batch)
# --------------------------------------------------------------------------

TRANS_BATCH_CHK_PMT = '''
你是一位专业翻译审校。下面是若干条原文与译文的 JSON 对，请逐条检查译文是否存在明显错误、遗漏或不符合目标语言表达习惯的问题。

## 输入格式（JSON 数组，顺序即编号）

[
  {"src": "原文0", "tgt": "译文0"},
  {"src": "原文1", "tgt": "译文1"}
]

## 输出要求

+   只输出一个 JSON 数组，不要包含其它任何文字。
+   长度与输入一致；每一条为 null 表示该条无需修改，否则为一个字符串数组，列出该条译文的问题。
+   示例：["", "该条译文生硬，不够通顺", null]
+   如果某条译文没有问题，对应位置输出 null 或空字符串。

## 待审校内容

{items_json}
'''

TRANS_BATCH_FIX_PMT = '''
你是一位专业翻译。请根据审校意见重新翻译下面的批次，保证内容原意不变，同时更符合目标语言表达习惯。

## 输入格式（JSON 数组，顺序即编号）

[
  {"src": "原文0", "tgt": "译文0", "checks": "问题列表或空字符串"},
  {"src": "原文1", "tgt": "译文1", "checks": "问题列表或空字符串"}
]

## 输出要求

+   只输出一个 JSON 数组，长度与输入完全一致，顺序一一对应。
+   每个元素是对应原文重新翻译后的译文（字符串）。
+   如果某条没有需要修改的问题，仍请原样输出该条译文。

## 待重新翻译内容

{items_json}
'''

__all__ = [
    "OCR_PMT",
    "TRANS_PMT",
    "TRANS_CHK_PMT",
    "TRANS_FIX_PMT",
    "TRANS_BATCH_PMT",
    "TRANS_BATCH_CHK_PMT",
    "TRANS_BATCH_FIX_PMT",
]