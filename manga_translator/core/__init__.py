"""
Core module for Manga Translator.
"""

from manga_translator.core.config import ConfigManager
from manga_translator.core.logger import setup_logger, get_logger
from manga_translator.core.translator import (
    TranslatorManager,
    TranslationEngine,
    TranslationResult,
    GoogleTranslator,
    DeepLTranslator,
    LibreTranslateEngine,
    MockTranslator,
)
from manga_translator.core.ocr import (
    OCRManager,
    OCREngine,
    TextRegion,
    TesseractEngine,
    PaddleOCREngine,
    EasyOCREngine,
    MockOCREngine,
)
from manga_translator.core.llm_client import (
    LLMClient,
    LLMConfigError,
    is_configured as llm_is_configured,
)
from manga_translator.core.llm_ocr import LLMOCREngine
from manga_translator.core.llm_translator import LLMTranslator

__all__ = [
    "ConfigManager",
    "setup_logger",
    "get_logger",
    "TranslatorManager",
    "TranslationEngine",
    "TranslationResult",
    "GoogleTranslator",
    "DeepLTranslator",
    "LibreTranslateEngine",
    "MockTranslator",
    "OCRManager",
    "OCREngine",
    "TextRegion",
    "TesseractEngine",
    "PaddleOCREngine",
    "EasyOCREngine",
    "MockOCREngine",
    "LLMClient",
    "LLMConfigError",
    "llm_is_configured",
    "LLMOCREngine",
    "LLMTranslator",
]