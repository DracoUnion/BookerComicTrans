"""
Core application module for Manga Translator.
"""

import sys
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QPixmap, QIcon, QFontDatabase

from manga_translator.ui.main_window import MainWindow
from manga_translator.core.config import ConfigManager
from manga_translator.core.logger import setup_logger
from manga_translator.core.translator import TranslatorManager
from manga_translator.core.ocr import OCRManager
from manga_translator.utils.resources import get_resource_path


class MangaTranslatorApp:
    """Main application class for Manga Translator."""

    def __init__(self, argv: list):
        self.argv = argv
        self.app: Optional[QApplication] = None
        self.main_window: Optional[MainWindow] = None
        self.config_manager: Optional[ConfigManager] = None
        self.translator_manager: Optional[TranslatorManager] = None
        self.ocr_manager: Optional[OCRManager] = None
        self.logger = None
        self.splash: Optional[QSplashScreen] = None

    def run(self) -> int:
        """Run the application."""
        # Initialize Qt Application
        self.app = QApplication(self.argv)
        self.app.setApplicationName("Manga Translator")
        self.app.setApplicationVersion("1.0.0")
        self.app.setOrganizationName("BookerComicTrans")
        self.app.setOrganizationDomain("bookercomictrans.local")

        # Load application font
        self._load_fonts()

        # Show splash screen
        self._show_splash()

        # Initialize core components
        self._initialize_core()

        # Create and show main window
        self._create_main_window()

        # Hide splash and show main window
        if self.splash:
            self.splash.finish(self.main_window)

        self.main_window.show()

        # Run the application
        return self.app.exec()

    def _load_fonts(self):
        """Load custom fonts."""
        # Load any custom fonts if needed
        font_dir = get_resource_path("fonts")
        if font_dir.exists():
            for font_file in font_dir.glob("*.ttf"):
                QFontDatabase.addApplicationFont(str(font_file))

    def _show_splash(self):
        """Show splash screen during startup."""
        splash_path = get_resource_path("images/splash.png")
        if splash_path.exists():
            pixmap = QPixmap(str(splash_path))
            self.splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
            self.splash.show()
            self.splash.showMessage(
                "Loading Manga Translator...",
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                Qt.GlobalColor.white
            )
            self.app.processEvents()

    def _initialize_core(self):
        """Initialize core components."""
        # Setup logging
        self.logger = setup_logger("MangaTranslator")
        self.logger.info("Initializing Manga Translator v1.0.0")

        # Initialize config manager
        self.config_manager = ConfigManager()
        self.logger.info("Configuration loaded")

        # Initialize OCR manager
        self.ocr_manager = OCRManager(self.config_manager)
        self.logger.info("OCR engine initialized")

        # Initialize translator manager
        self.translator_manager = TranslatorManager(self.config_manager)
        self.logger.info("Translation engines initialized")

    def _create_main_window(self):
        """Create the main application window."""
        self.main_window = MainWindow(
            config_manager=self.config_manager,
            translator_manager=self.translator_manager,
            ocr_manager=self.ocr_manager,
        )

        # Apply theme
        self._apply_theme()

    def _apply_theme(self):
        """Apply application theme."""
        theme = self.config_manager.get("ui.theme", "system")
        if theme == "dark":
            self._apply_dark_theme()
        elif theme == "light":
            self._apply_light_theme()
        # "system" uses default system theme

    def _apply_dark_theme(self):
        """Apply dark theme."""
        dark_stylesheet = """
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QMenuBar {
            background-color: #2d2d2d;
            color: #ffffff;
        }
        QMenuBar::item:selected {
            background-color: #3d3d3d;
        }
        QMenu {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #3d3d3d;
        }
        QMenu::item:selected {
            background-color: #3d3d3d;
        }
        QToolBar {
            background-color: #2d2d2d;
            border: none;
            spacing: 4px;
        }
        QStatusBar {
            background-color: #2d2d2d;
            color: #ffffff;
        }
        QPushButton {
            background-color: #3d3d3d;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #4d4d4d;
            border-color: #666666;
        }
        QPushButton:pressed {
            background-color: #2d2d2d;
        }
        QPushButton:disabled {
            background-color: #1e1e1e;
            color: #666666;
        }
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 4px;
        }
        QComboBox {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #2d2d2d;
            color: #ffffff;
            selection-background-color: #3d3d3d;
        }
        QListWidget, QTreeWidget, QTableWidget {
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #555555;
        }
        QHeaderView::section {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 4px;
        }
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background-color: #555555;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #666666;
        }
        QTabWidget::pane {
            border: 1px solid #555555;
            background-color: #1e1e1e;
        }
        QTabBar::tab {
            background-color: #2d2d2d;
            color: #ffffff;
            padding: 8px 16px;
            border: 1px solid #555555;
        }
        QTabBar::tab:selected {
            background-color: #3d3d3d;
        }
        QGroupBox {
            border: 1px solid #555555;
            border-radius: 4px;
            margin-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }
        """
        self.app.setStyleSheet(dark_stylesheet)

    def _apply_light_theme(self):
        """Apply light theme."""
        light_stylesheet = """
        QMainWindow, QWidget {
            background-color: #f5f5f5;
            color: #333333;
        }
        QMenuBar {
            background-color: #ffffff;
            color: #333333;
        }
        QMenuBar::item:selected {
            background-color: #e0e0e0;
        }
        QMenu {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
        }
        QMenu::item:selected {
            background-color: #e0e0e0;
        }
        QToolBar {
            background-color: #ffffff;
            border: none;
            spacing: 4px;
        }
        QStatusBar {
            background-color: #ffffff;
            color: #333333;
        }
        QPushButton {
            background-color: #e0e0e0;
            color: #333333;
            border: 1px solid #cccccc;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #d0d0d0;
            border-color: #bbbbbb;
        }
        QPushButton:pressed {
            background-color: #c0c0c0;
        }
        QPushButton:disabled {
            background-color: #f5f5f5;
            color: #999999;
        }
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 4px;
        }
        QComboBox {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #333333;
            selection-background-color: #e0e0e0;
        }
        QListWidget, QTreeWidget, QTableWidget {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            color: #333333;
            border: 1px solid #cccccc;
            padding: 4px;
        }
        QScrollBar:vertical {
            background-color: #f5f5f5;
            width: 12px;
            border: none;
        }
        QScrollBar::handle:vertical {
            background-color: #cccccc;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #bbbbbb;
        }
        QTabWidget::pane {
            border: 1px solid #cccccc;
            background-color: #ffffff;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            color: #333333;
            padding: 8px 16px;
            border: 1px solid #cccccc;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom-color: #ffffff;
        }
        QGroupBox {
            border: 1px solid #cccccc;
            border-radius: 4px;
            margin-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }
        """
        self.app.setStyleSheet(light_stylesheet)