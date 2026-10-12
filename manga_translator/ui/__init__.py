"""
UI module for Manga Translator.
"""

from manga_translator.ui.main_window import MainWindow
from manga_translator.ui.image_viewer import ImageViewer
from manga_translator.ui.settings_dialog import SettingsDialog
from manga_translator.ui.widgets import (
    TranslationOverlay,
    PageListWidget,
    TranslationPanel,
    StatusIndicator,
)

__all__ = [
    "MainWindow",
    "ImageViewer",
    "SettingsDialog",
    "TranslationOverlay",
    "PageListWidget",
    "TranslationPanel",
    "StatusIndicator",
]