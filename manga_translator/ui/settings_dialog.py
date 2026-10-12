"""
Settings dialog for Manga Translator.
"""

from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QPushButton, QLabel, QDialogButtonBox, QGroupBox, QFileDialog,
    QDoubleSpinBox, QMessageBox, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt

from manga_translator.core.config import ConfigManager
from manga_translator.core.translator import TranslatorManager
from manga_translator.core.ocr import OCRManager
from manga_translator.core.logger import get_logger


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, config_manager: ConfigManager,
                 translator_manager: TranslatorManager,
                 ocr_manager: OCRManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.translator_manager = translator_manager
        self.ocr_manager = ocr_manager
        self.logger = get_logger("SettingsDialog")

        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 500)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_general_tab(), "General")
        self.tabs.addTab(self._create_ocr_tab(), "OCR")
        self.tabs.addTab(self._create_translation_tab(), "Translation")
        self.tabs.addTab(self._create_image_tab(), "Image")
        self.tabs.addTab(self._create_export_tab(), "Export")
        layout.addWidget(self.tabs)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(button_box)

    def _create_general_tab(self) -> QWidget:
        """Create the General tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["system", "light", "dark"])
        layout.addRow("Theme:", self.theme_combo)

        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItems(["en", "ja", "zh", "ko"])
        layout.addRow("UI Language:", self.language_combo)

        # Toolbar/Statusbar
        self.show_toolbar_cb = QCheckBox("Show toolbar")
        layout.addRow("", self.show_toolbar_cb)

        self.show_statusbar_cb = QCheckBox("Show status bar")
        layout.addRow("", self.show_statusbar_cb)

        return widget

    def _create_ocr_tab(self) -> QWidget:
        """Create the OCR tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Engine
        self.ocr_engine_combo = QComboBox()
        available = self.ocr_manager.get_available_engines()
        if not available:
            available = ["mock"]
        self.ocr_engine_combo.addItems(available)
        layout.addRow("OCR Engine:", self.ocr_engine_combo)

        # Language
        self.ocr_language_combo = QComboBox()
        self.ocr_language_combo.addItems([
            "jpn", "eng", "chi_sim", "chi_tra", "kor",
            "deu", "fra", "spa", "rus",
        ])
        layout.addRow("Language:", self.ocr_language_combo)

        # Tesseract path
        tesseract_layout = QHBoxLayout()
        self.tesseract_path_edit = QLineEdit()
        self.tesseract_path_edit.setPlaceholderText("Path to tesseract.exe (optional)")
        tesseract_layout.addWidget(self.tesseract_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_tesseract)
        tesseract_layout.addWidget(browse_btn)
        layout.addRow("Tesseract Path:", tesseract_layout)

        # Confidence threshold
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(0, 100)
        self.confidence_spin.setSuffix("%")
        layout.addRow("Confidence Threshold:", self.confidence_spin)

        # Preprocess
        self.preprocess_cb = QCheckBox("Preprocess images (enhance contrast, sharpen)")
        layout.addRow("", self.preprocess_cb)

        return widget

    def _create_translation_tab(self) -> QWidget:
        """Create the Translation tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Engine
        self.trans_engine_combo = QComboBox()
        engines = self.translator_manager.get_available_engines()
        if not engines:
            engines = ["mock"]
        self.trans_engine_combo.addItems(engines)
        layout.addRow("Translation Engine:", self.trans_engine_combo)

        # Source language
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["auto", "ja", "zh", "ko", "en"])
        layout.addRow("Source Language:", self.source_lang_combo)

        # Target language
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["en", "ja", "zh", "ko", "fr", "de", "es"])
        layout.addRow("Target Language:", self.target_lang_combo)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("API key (for DeepL/LibreTranslate)")
        layout.addRow("API Key:", self.api_key_edit)

        # Cache
        self.cache_cb = QCheckBox("Cache translations")
        layout.addRow("", self.cache_cb)

        return widget

    def _create_image_tab(self) -> QWidget:
        """Create the Image tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Max image size
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(512, 16384)
        self.max_size_spin.setSingleStep(256)
        self.max_size_spin.setSuffix(" px")
        layout.addRow("Max Image Size:", self.max_size_spin)

        # Auto rotate
        self.auto_rotate_cb = QCheckBox("Auto-rotate based on EXIF")
        layout.addRow("", self.auto_rotate_cb)

        return widget

    def _create_export_tab(self) -> QWidget:
        """Create the Export tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Format
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["png", "jpg", "pdf", "cbz"])
        layout.addRow("Export Format:", self.export_format_combo)

        # Quality
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setSuffix("%")
        layout.addRow("JPEG Quality:", self.quality_spin)

        # Include original
        self.include_original_cb = QCheckBox("Include original image alongside translation")
        layout.addRow("", self.include_original_cb)

        # Output directory
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Default: same as source")
        output_layout.addWidget(self.output_dir_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(browse_btn)
        layout.addRow("Output Directory:", output_layout)

        return widget

    def _browse_tesseract(self):
        """Browse for tesseract executable."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tesseract Executable", "",
            "Executable (*.exe);;All Files (*)"
        )
        if path:
            self.tesseract_path_edit.setText(path)

    def _browse_output_dir(self):
        """Browse for output directory."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_dir_edit.setText(path)

    def _load_settings(self):
        """Load current settings into the widgets."""
        # General
        theme = self.config.get("ui.theme", "system")
        idx = self.theme_combo.findText(theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

        lang = self.config.get("ui.language", "en")
        idx = self.language_combo.findText(lang)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

        self.show_toolbar_cb.setChecked(self.config.get("ui.show_toolbar", True))
        self.show_statusbar_cb.setChecked(self.config.get("ui.show_statusbar", True))

        # OCR
        ocr_engine = self.config.get("ocr.engine", "tesseract")
        idx = self.ocr_engine_combo.findText(ocr_engine)
        if idx >= 0:
            self.ocr_engine_combo.setCurrentIndex(idx)

        ocr_lang = self.config.get("ocr.language", "jpn")
        idx = self.ocr_language_combo.findText(ocr_lang)
        if idx >= 0:
            self.ocr_language_combo.setCurrentIndex(idx)

        self.tesseract_path_edit.setText(self.config.get("ocr.tesseract_path", ""))
        self.confidence_spin.setValue(self.config.get("ocr.confidence_threshold", 60))
        self.preprocess_cb.setChecked(self.config.get("ocr.preprocess", True))

        # Translation
        trans_engine = self.config.get("translation.engine", "google")
        idx = self.trans_engine_combo.findText(trans_engine)
        if idx >= 0:
            self.trans_engine_combo.setCurrentIndex(idx)

        src = self.config.get("translation.source_language", "auto")
        idx = self.source_lang_combo.findText(src)
        if idx >= 0:
            self.source_lang_combo.setCurrentIndex(idx)

        tgt = self.config.get("translation.target_language", "en")
        idx = self.target_lang_combo.findText(tgt)
        if idx >= 0:
            self.target_lang_combo.setCurrentIndex(idx)

        self.api_key_edit.setText(self.config.get("translation.api_key", ""))
        self.cache_cb.setChecked(self.config.get("translation.use_cache", True))

        # Image
        self.max_size_spin.setValue(self.config.get("image.max_image_size", 4096))
        self.auto_rotate_cb.setChecked(self.config.get("image.auto_rotate", True))

        # Export
        fmt = self.config.get("export.format", "png")
        idx = self.export_format_combo.findText(fmt)
        if idx >= 0:
            self.export_format_combo.setCurrentIndex(idx)

        self.quality_spin.setValue(self.config.get("export.quality", 90))
        self.include_original_cb.setChecked(self.config.get("export.include_original", False))
        self.output_dir_edit.setText(self.config.get("export.output_directory", ""))

    def _save_settings(self):
        """Save settings from widgets to config."""
        # General
        self.config.set("ui.theme", self.theme_combo.currentText())
        self.config.set("ui.language", self.language_combo.currentText())
        self.config.set("ui.show_toolbar", self.show_toolbar_cb.isChecked())
        self.config.set("ui.show_statusbar", self.show_statusbar_cb.isChecked())

        # OCR
        self.config.set("ocr.engine", self.ocr_engine_combo.currentText())
        self.config.set("ocr.language", self.ocr_language_combo.currentText())
        self.config.set("ocr.tesseract_path", self.tesseract_path_edit.text())
        self.config.set("ocr.confidence_threshold", self.confidence_spin.value())
        self.config.set("ocr.preprocess", self.preprocess_cb.isChecked())

        # Translation
        self.config.set("translation.engine", self.trans_engine_combo.currentText())
        self.config.set("translation.source_language", self.source_lang_combo.currentText())
        self.config.set("translation.target_language", self.target_lang_combo.currentText())
        self.config.set("translation.api_key", self.api_key_edit.text())
        self.config.set("translation.use_cache", self.cache_cb.isChecked())

        # Image
        self.config.set("image.max_image_size", self.max_size_spin.value())
        self.config.set("image.auto_rotate", self.auto_rotate_cb.isChecked())

        # Export
        self.config.set("export.format", self.export_format_combo.currentText())
        self.config.set("export.quality", self.quality_spin.value())
        self.config.set("export.include_original", self.include_original_cb.isChecked())
        self.config.set("export.output_directory", self.output_dir_edit.text())

        self.config.save()

    def _apply_engine_settings(self):
        """Apply engine settings (reinitialize engines)."""
        # Reinit OCR engine
        ocr_engine = self.ocr_engine_combo.currentText()
        self.ocr_manager.set_engine(ocr_engine)
        self.ocr_manager.set_language(self.ocr_language_combo.currentText())

        # Reinit translation engine
        trans_engine = self.trans_engine_combo.currentText()
        self.translator_manager.set_engine(trans_engine)

        api_key = self.api_key_edit.text()
        if api_key:
            self.translator_manager.set_api_key(trans_engine, api_key)

    def _on_apply(self):
        """Handle Apply button."""
        self._save_settings()
        self._apply_engine_settings()
        self.logger.info("Settings applied")

    def _on_accept(self):
        """Handle OK button."""
        self._save_settings()
        self._apply_engine_settings()
        self.logger.info("Settings saved")
        self.accept()