"""
Resource utilities for Manga Translator.
"""

from pathlib import Path
import sys


def get_resource_path(relative_path: str = "") -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent.parent

    return base_path / "resources" / relative_path


def get_data_path(relative_path: str = "") -> Path:
    """Get absolute path to data directory."""
    from PySide6.QtCore import QStandardPaths
    data_dir = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )) / "MangaTranslator"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / relative_path


def get_cache_path(relative_path: str = "") -> Path:
    """Get absolute path to cache directory."""
    from PySide6.QtCore import QStandardPaths
    cache_dir = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.CacheLocation
    )) / "MangaTranslator"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / relative_path


def get_config_path() -> Path:
    """Get configuration file path."""
    return get_data_path("config.json")