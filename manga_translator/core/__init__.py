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
]