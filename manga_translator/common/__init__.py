"""
Common zero-Qt building blocks for Manga Translator.

This package has no PySide6 dependency: it can be imported and unit-tested
without a display server, keeping the architectural rule that only
``manga_translator.ui`` may import Qt bindings.
"""

from manga_translator.common.exceptions import (
    MangaTranslatorError,
    AppError,
    ConfigError,
    TransformError,
    StorageError,
)
from manga_translator.common.events import EventHub
from manga_translator.common.context import AppContext

__all__ = [
    "MangaTranslatorError",
    "AppError",
    "ConfigError",
    "TransformError",
    "StorageError",
    "EventHub",
    "AppContext",
]