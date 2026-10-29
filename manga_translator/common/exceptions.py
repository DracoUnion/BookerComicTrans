"""
Domain exception hierarchy for Manga Translator.

Zero-Qt, importable and testable anywhere.
"""


class MangaTranslatorError(Exception):
    """Base class for all domain errors."""


class AppError(MangaTranslatorError):
    """Application-level configuration / startup error."""


class ConfigError(AppError):
    """Raised when a configuration value is missing or invalid."""


class TransformError(MangaTranslatorError):
    """Raised when a page cannot be OCR'd, translated or rendered."""


class StorageError(MangaTranslatorError):
    """Raised when reading or writing persisted files fails."""