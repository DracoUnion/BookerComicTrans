"""
Configuration management for Manga Translator.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QSettings, QStandardPaths


class ConfigManager:
    """Manages application configuration."""

    DEFAULT_CONFIG = {
        "ui": {
            "theme": "system",  # system, light, dark
            "language": "en",
            "window_geometry": None,
            "window_state": None,
            "show_toolbar": True,
            "show_statusbar": True,
        },
        "ocr": {
            "engine": "tesseract",  # tesseract, paddleocr, easyocr
            "language": "jpn",  # jpn, chi_sim, chi_tra, kor, eng
            "tesseract_path": "",
            "confidence_threshold": 60,
            "preprocess": True,
        },
        "translation": {
            "engine": "google",  # google, deepl, bing, libretranslate, llm
            "source_language": "ja",  # ja, zh, ko, auto
            "target_language": "en",
            "api_key": "",
            "api_secret": "",
            "use_cache": True,
            "llm_rounds": 1,  # translate->review->fix iterations (LLM engine)
        },
        "image": {
            "supported_formats": [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"],
            "max_image_size": 4096,
            "auto_rotate": True,
        },
        "export": {
            "format": "png",  # png, jpg, pdf, cbz
            "quality": 90,
            "include_original": False,
            "output_directory": "",
        },
        "hotkeys": {
            "next_page": "Right",
            "prev_page": "Left",
            "translate": "T",
            "toggle_bilingual": "B",
            "zoom_in": "Ctrl++",
            "zoom_out": "Ctrl+-",
            "fit_width": "W",
            "fit_height": "H",
        },
    }

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._get_default_config_path()
        self.config: Dict[str, Any] = {}
        self.settings = QSettings("BookerComicTrans", "MangaTranslator")
        self.load()

    def _get_default_config_path(self) -> str:
        """Get default configuration file path."""
        config_dir = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )) / "MangaTranslator"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "config.json")

    def load(self) -> Dict[str, Any]:
        """Load configuration from file and QSettings."""
        # Start with defaults
        self.config = self._deep_copy(self.DEFAULT_CONFIG)

        # Load from JSON file if exists
        if Path(self.config_file).exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                self._deep_merge(self.config, file_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config file: {e}")

        # Override with QSettings (for window geometry/state)
        self._load_from_qsettings()

        return self.config

    def _load_from_qsettings(self):
        """Load settings from QSettings."""
        # Window geometry and state
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.config["ui"]["window_geometry"] = geometry

        state = self.settings.value("window/state")
        if state:
            self.config["ui"]["window_state"] = state

        # Recent files
        recent_files = self.settings.value("recentFiles", [])
        if recent_files:
            self.config["recent_files"] = recent_files

    def save(self):
        """Save configuration to file and QSettings."""
        # Save to JSON file
        try:
            config_dir = Path(self.config_file).parent
            config_dir.mkdir(parents=True, exist_ok=True)

            # Don't save window geometry/state to JSON (use QSettings)
            config_to_save = self._deep_copy(self.config)
            config_to_save["ui"]["window_geometry"] = None
            config_to_save["ui"]["window_state"] = None

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Warning: Failed to save config file: {e}")

        # Save window geometry/state to QSettings
        if self.config["ui"]["window_geometry"]:
            self.settings.setValue("window/geometry", self.config["ui"]["window_geometry"])
        if self.config["ui"]["window_state"]:
            self.settings.setValue("window/state", self.config["ui"]["window_state"])

        # Save recent files
        if "recent_files" in self.config:
            self.settings.setValue("recentFiles", self.config["recent_files"])

        self.settings.sync()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'ui.theme')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set configuration value using dot notation."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def update(self, updates: Dict[str, Any]):
        """Update multiple configuration values."""
        self._deep_merge(self.config, updates)

    def reset(self):
        """Reset configuration to defaults."""
        self.config = self._deep_copy(self.DEFAULT_CONFIG)

    def add_recent_file(self, file_path: str):
        """Add a file to recent files list."""
        recent = self.config.get("recent_files", [])
        if file_path in recent:
            recent.remove(file_path)
        recent.insert(0, file_path)
        self.config["recent_files"] = recent[:10]  # Keep only 10 recent files

    def get_recent_files(self) -> list:
        """Get list of recent files."""
        return self.config.get("recent_files", [])

    def _deep_copy(self, obj: Any) -> Any:
        """Deep copy a dictionary/list."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(v) for v in obj]
        else:
            return obj

    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge source into target."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value