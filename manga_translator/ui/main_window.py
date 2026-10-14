"""
Main application window for Manga Translator.
"""

import os
from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QMenu, QMenuBar, QFileDialog, QMessageBox,
    QLabel, QProgressBar, QPushButton, QComboBox,
    QDockWidget, QTabWidget, QApplication, QTableWidgetItem,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings, QThread
from PyQt6.QtGui import (
    QAction, QIcon, QKeySequence, QPixmap, QImage, QActionGroup, QShortcut,
)

from PIL import Image

from manga_translator.core.config import ConfigManager
from manga_translator.core.translator import TranslatorManager, TranslationResult
from manga_translator.core.ocr import OCRManager, TextRegion
from manga_translator.core.image_processor import ImageProcessor
from manga_translator.core.logger import get_logger
from manga_translator.ui.image_viewer import ImageViewer
from manga_translator.ui.widgets import (
    PageListWidget, TranslationPanel, StatusIndicator, ImageDropArea,
)
from manga_translator.ui.settings_dialog import SettingsDialog
from manga_translator.ui.workers import (
    OCRWorker, TranslationWorker, PipelineWorker, ImageLoadWorker,
)
from manga_translator.utils.resources import get_resource_path


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config_manager: ConfigManager,
                 translator_manager: TranslatorManager,
                 ocr_manager: OCRManager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.translator_manager = translator_manager
        self.ocr_manager = ocr_manager
        self.image_processor = ImageProcessor()
        self.logger = get_logger("MainWindow")

        # State
        self._pages: List[Path] = []
        self._current_index: int = -1
        self._current_image: Optional[Image.Image] = None
        self._current_regions: List[TextRegion] = []
        self._current_translations: List[TranslationResult] = []
        self._current_worker: Optional[QThread] = None
        # Strong references to every live worker so Qt threads are never
        # garbage-collected while still running (which aborts the process).
        self._active_workers: set = set()

        self.setWindowTitle("Manga Translator")
        self.setWindowIcon(self._load_icon())
        self.resize(1400, 900)

        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._restore_geometry()

        self._update_actions()

    # ---------------------------------------------------------------- UI setup

    def _load_icon(self) -> QIcon:
        """Load the application icon."""
        icon_path = get_resource_path("images/icon.png")
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    def _setup_ui(self):
        """Set up the central UI."""
        # Central splitter: page list | viewer | side panel
        self.central_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: page list dock content
        self.page_list = PageListWidget()
        self.page_list.page_selected.connect(self._on_page_selected)
        self.central_splitter.addWidget(self.page_list)

        # Center: viewer area (stack viewer / drop area)
        self.viewer_container = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)

        self.drop_area = ImageDropArea()
        self.drop_area.files_dropped.connect(self._on_files_dropped)
        viewer_layout.addWidget(self.drop_area)

        self.viewer = ImageViewer()
        self.viewer.region_selected.connect(self._on_region_selected)
        self.viewer.region_clicked.connect(self._on_overlay_clicked)
        self.viewer.zoom_changed.connect(self._on_zoom_changed)
        self.viewer.hide()
        viewer_layout.addWidget(self.viewer)

        self.central_splitter.addWidget(self.viewer_container)

        # Right: translation panel
        self.translation_panel = TranslationPanel()
        self.translation_panel.retranslate_requested.connect(self._on_retranslate_one)
        self.translation_panel.export_btn.clicked.connect(self._on_export)
        self.central_splitter.addWidget(self.translation_panel)

        self.central_splitter.setStretchFactor(0, 0)
        self.central_splitter.setStretchFactor(1, 1)
        self.central_splitter.setStretchFactor(2, 0)
        self.central_splitter.setSizes([180, 900, 320])

        self.setCentralWidget(self.central_splitter)

    def _setup_menus(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        self.open_action = QAction("&Open Images...", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self._on_open_files)
        file_menu.addAction(self.open_action)

        self.open_folder_action = QAction("Open &Folder...", self)
        self.open_folder_action.setShortcut("Ctrl+Shift+O")
        self.open_folder_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(self.open_folder_action)

        # Recent files submenu
        self.recent_menu = file_menu.addMenu("Open &Recent")
        self._update_recent_menu()

        file_menu.addSeparator()

        self.export_action = QAction("&Export...", self)
        self.export_action.setShortcut("Ctrl+E")
        self.export_action.triggered.connect(self._on_export)
        file_menu.addAction(self.export_action)

        self.export_all_action = QAction("Export &All Pages...", self)
        self.export_all_action.setShortcut("Ctrl+Shift+E")
        self.export_all_action.triggered.connect(self._on_export_all)
        file_menu.addAction(self.export_all_action)

        file_menu.addSeparator()

        self.close_action = QAction("&Close Images", self)
        self.close_action.triggered.connect(self._on_close_files)
        file_menu.addAction(self.close_action)

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.translate_action = QAction("&Translate Page", self)
        self.translate_action.setShortcut("T")
        self.translate_action.triggered.connect(self._on_translate_page)
        edit_menu.addAction(self.translate_action)

        self.translate_all_action = QAction("Translate &All Pages", self)
        self.translate_all_action.setShortcut("Ctrl+T")
        self.translate_all_action.triggered.connect(self._on_translate_all)
        edit_menu.addAction(self.translate_all_action)

        edit_menu.addSeparator()

        self.select_region_action = QAction("&Select Region", self)
        self.select_region_action.setCheckable(True)
        self.select_region_action.setShortcut("R")
        self.select_region_action.triggered.connect(self._on_toggle_select_mode)
        edit_menu.addAction(self.select_region_action)

        self.clear_overlays_action = QAction("&Clear Overlays", self)
        self.clear_overlays_action.setShortcut("Ctrl+Shift+C")
        self.clear_overlays_action.triggered.connect(self._on_clear_overlays)
        edit_menu.addAction(self.clear_overlays_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_in_action.triggered.connect(lambda: self.viewer.zoom_in())
        view_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.zoom_out_action.triggered.connect(lambda: self.viewer.zoom_out())
        view_menu.addAction(self.zoom_out_action)

        self.fit_window_action = QAction("&Fit to Window", self)
        self.fit_window_action.setShortcut("Ctrl+0")
        self.fit_window_action.triggered.connect(lambda: self.viewer.fit_to_window())
        view_menu.addAction(self.fit_window_action)

        self.fit_width_action = QAction("Fit &Width", self)
        self.fit_width_action.setShortcut("W")
        self.fit_width_action.triggered.connect(lambda: self.viewer.fit_width())
        view_menu.addAction(self.fit_width_action)

        self.fit_height_action = QAction("Fit &Height", self)
        self.fit_height_action.setShortcut("H")
        self.fit_height_action.triggered.connect(lambda: self.viewer.fit_height())
        view_menu.addAction(self.fit_height_action)

        self.reset_zoom_action = QAction("&100%", self)
        self.reset_zoom_action.setShortcut("Ctrl+1")
        self.reset_zoom_action.triggered.connect(lambda: self.viewer.reset_zoom())
        view_menu.addAction(self.reset_zoom_action)

        view_menu.addSeparator()

        self.toggle_bilingual_action = QAction("Show &Bilingual", self)
        self.toggle_bilingual_action.setCheckable(True)
        self.toggle_bilingual_action.setShortcut("B")
        self.toggle_bilingual_action.triggered.connect(self._on_toggle_bilingual)
        view_menu.addAction(self.toggle_bilingual_action)

        view_menu.addSeparator()

        self.prev_page_action = QAction("&Previous Page", self)
        self.prev_page_action.setShortcut(QKeySequence.StandardKey.MoveToPreviousPage if hasattr(QKeySequence.StandardKey, 'MoveToPreviousPage') else "PgUp")
        self.prev_page_action.triggered.connect(self._on_prev_page)
        view_menu.addAction(self.prev_page_action)

        self.next_page_action = QAction("&Next Page", self)
        self.next_page_action.setShortcut("PgDown")
        self.next_page_action.triggered.connect(self._on_next_page)
        view_menu.addAction(self.next_page_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        self.settings_action = QAction("&Settings...", self)
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.triggered.connect(self._on_settings)
        tools_menu.addAction(self.settings_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        about_qt_action = QAction("About &Qt", self)
        about_qt_action.triggered.connect(lambda: QApplication.aboutQt())
        help_menu.addAction(about_qt_action)

    def _setup_toolbar(self):
        """Set up the toolbar."""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(self.toolbar)

        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.open_folder_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.translate_action)
        self.toolbar.addAction(self.select_region_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.fit_window_action)
        self.toolbar.addSeparator()

        # OCR engine selector
        self.toolbar.addWidget(QLabel(" OCR: "))
        self.ocr_engine_combo = QComboBox()
        self.ocr_engine_combo.addItems(self.ocr_manager.get_available_engines())
        self.ocr_engine_combo.currentTextChanged.connect(self._on_ocr_engine_changed)
        self.ocr_engine_combo.setMinimumWidth(120)
        self.toolbar.addWidget(self.ocr_engine_combo)

        # Translation engine selector
        self.toolbar.addWidget(QLabel(" Translate: "))
        self.trans_engine_combo = QComboBox()
        self.trans_engine_combo.addItems(self.translator_manager.get_available_engines())
        self.trans_engine_combo.currentTextChanged.connect(self._on_trans_engine_changed)
        self.trans_engine_combo.setMinimumWidth(120)
        self.toolbar.addWidget(self.trans_engine_combo)

        # Source / target language
        self.toolbar.addWidget(QLabel("  "))
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(["auto", "ja", "zh", "ko", "en"])
        self.source_lang_combo.setCurrentText(self.config.get("translation.source_language", "auto"))
        self.source_lang_combo.currentTextChanged.connect(
            lambda t: self.config.set("translation.source_language", t))
        self.toolbar.addWidget(self.source_lang_combo)

        arrow = QLabel(" → ")
        self.toolbar.addWidget(arrow)

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["en", "ja", "zh", "ko", "fr", "de", "es"])
        self.target_lang_combo.setCurrentText(self.config.get("translation.target_language", "en"))
        self.target_lang_combo.currentTextChanged.connect(
            lambda t: self.config.set("translation.target_language", t))
        self.toolbar.addWidget(self.target_lang_combo)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_indicator = StatusIndicator("Ready", "idle")
        self.statusbar.addWidget(self.status_indicator)

        self.statusbar.addPermanentWidget(QLabel("Zoom:"))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)
        self.statusbar.addPermanentWidget(self.zoom_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

    def _setup_shortcuts(self):
        """Set up additional keyboard shortcuts."""
        # Page navigation
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._on_next_page)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._on_prev_page)

    # ------------------------------------------------------------- File actions

    def _on_open_files(self):
        """Open image files."""
        formats = self.config.get("image.supported_formats",
                                  [".jpg", ".png", ".webp", ".bmp"])
        filter_str = "Images (" + " ".join(f"*{f}" for f in formats) + ");;All Files (*)"
        files, _ = QFileDialog.getOpenFileNames(self, "Open Images", "", filter_str)
        if files:
            self._load_files([Path(f) for f in files])

    def _on_open_folder(self):
        """Open a folder of images."""
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder:
            return
        formats = set(self.config.get("image.supported_formats",
                                      [".jpg", ".png", ".webp", ".bmp"]))
        folder_path = Path(folder)
        files = sorted(
            p for p in folder_path.iterdir()
            if p.is_file() and p.suffix.lower() in formats
        )
        if files:
            self._load_files(files)
        else:
            QMessageBox.information(self, "No Images",
                                    f"No supported images found in {folder}")

    def _on_files_dropped(self, paths: List[str]):
        """Handle files dropped onto the drop area."""
        formats = set(self.config.get("image.supported_formats", [".jpg", ".png"]))
        files = []
        for p in paths:
            path = Path(p)
            if path.is_file() and path.suffix.lower() in formats:
                files.append(path)
            elif path.is_dir():
                files.extend(sorted(
                    f for f in path.iterdir()
                    if f.is_file() and f.suffix.lower() in formats
                ))
        if files:
            self._load_files(files)

    def _load_files(self, paths: List[Path]):
        """Load a list of image files."""
        self._pages = list(paths)
        self.page_list.set_pages(self._pages)
        self._current_index = -1

        # Register recent
        if self._pages:
            self.config.add_recent_file(str(self._pages[0].parent))
            self.config.save()
            self._update_recent_menu()

        # Show viewer
        self.drop_area.hide()
        self.viewer.show()

        # Load thumbnails in the background
        self._load_thumbnails()

        # Select first page (fires _on_page_selected via the signal)
        if self._pages:
            self.page_list.set_current_index(0)

    def _load_thumbnails(self):
        """Load thumbnails for all pages in the background."""
        for i in range(min(len(self._pages), 100)):  # limit for performance
            QTimer.singleShot(i * 30, lambda idx=i: self._load_thumbnail(idx))

    def _load_thumbnail(self, index: int):
        """Load a single thumbnail."""
        if index >= len(self._pages):
            return
        worker = ImageLoadWorker(self._pages[index], make_thumbnail=True)
        worker.thumbnail_ready.connect(
            lambda qimg, idx=index: self._on_thumbnail_ready(idx, qimg))
        self._start_worker(worker)

    def _on_thumbnail_ready(self, index: int, qimage: QImage):
        """Handle a loaded thumbnail."""
        self.page_list.set_thumbnail(index, QPixmap.fromImage(qimage))

    def _on_close_files(self):
        """Close all loaded files."""
        self._pages = []
        self.page_list.set_pages([])
        self.translation_panel.clear()
        self.viewer.clear_scene()
        self.viewer.hide()
        self.drop_area.show()
        self._current_index = -1
        self._current_image = None
        self._current_regions = []
        self._current_translations = []
        self._update_actions()

    def _update_recent_menu(self):
        """Update the recent files menu."""
        self.recent_menu.clear()
        recent = self.config.get_recent_files()
        if not recent:
            action = QAction("(no recent files)", self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)
            return
        for path in recent:
            action = QAction(path, self)
            action.triggered.connect(lambda checked, p=path: self._on_open_recent(p))
            self.recent_menu.addAction(action)

    def _on_open_recent(self, path: str):
        """Open a recent path."""
        p = Path(path)
        if p.is_dir():
            formats = set(self.config.get("image.supported_formats", [".jpg", ".png"]))
            files = sorted(f for f in p.iterdir()
                           if f.is_file() and f.suffix.lower() in formats)
            if files:
                self._load_files(files)
        elif p.is_file():
            self._load_files([p])

    # ----------------------------------------------------------- Page handling

    def _on_page_selected(self, index: int):
        """Handle page selection."""
        if index < 0 or index >= len(self._pages):
            return
        self._current_index = index
        path = self._pages[index]

        self.status_indicator.set_status("busy", f"Loading {path.name}...")

        # Cancel any in-flight load before starting a new one
        self._stop_worker(self._current_worker, 3000)

        worker = ImageLoadWorker(path, make_thumbnail=False)
        worker.loaded.connect(self._on_image_loaded)
        worker.error.connect(self._on_image_error)
        self._current_worker = worker
        self._start_worker(worker)

        self._update_actions()

    def _on_image_loaded(self, image: Image.Image):
        """Handle a loaded full image."""
        self._current_image = image
        self._current_regions = []
        self._current_translations = []

        # Convert to QImage
        qimage = self._pil_to_qimage(image)
        self.viewer.load_image(qimage)
        self.translation_panel.clear()

        name = self._pages[self._current_index].name if self._current_index >= 0 else ""
        self.status_indicator.set_status("success", f"{name} ({image.width}×{image.height})")
        self._update_actions()

    def _on_image_error(self, msg: str):
        """Handle image load error."""
        self.status_indicator.set_status("error", f"Error: {msg}")
        QMessageBox.warning(self, "Load Error", f"Failed to load image:\n{msg}")

    def _on_prev_page(self):
        """Go to the previous page."""
        if self._current_index > 0:
            self.page_list.set_current_index(self._current_index - 1)

    def _on_next_page(self):
        """Go to the next page."""
        if self._current_index < len(self._pages) - 1:
            self.page_list.set_current_index(self._current_index + 1)

    # ---------------------------------------------------------- Translation flow

    def _on_translate_page(self):
        """Translate the current page."""
        if self._current_image is None:
            QMessageBox.information(self, "No Image", "Please open an image first.")
            return

        self._start_pipeline(self._current_image)

    def _on_translate_all(self):
        """Translate all pages."""
        if not self._pages:
            QMessageBox.information(self, "No Images", "Please open images first.")
            return

        reply = QMessageBox.question(
            self, "Translate All",
            f"Translate all {len(self._pages)} pages? This may take a while.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Save current results before batch processing
        self._batch_translate(list(self._pages))

    def _start_pipeline(self, image: Image.Image):
        """Start the OCR + translation pipeline."""
        self._stop_worker(self._current_worker, 3000)

        self.status_indicator.set_status("busy", "Processing...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        worker = PipelineWorker(
            self.ocr_manager, self.translator_manager, image,
            self.source_lang_combo.currentText(),
            self.target_lang_combo.currentText(),
            self.config.get("ocr.preprocess", True),
        )
        worker.progress.connect(self._on_pipeline_progress)
        worker.ocr_finished.connect(self._on_ocr_finished)
        worker.translation_finished.connect(self._on_translation_finished)
        worker.error.connect(self._on_pipeline_error)
        worker.finished_all.connect(self._on_pipeline_done)
        self._current_worker = worker
        self._start_worker(worker)

    def _on_pipeline_progress(self, percent: int, message: str):
        """Update pipeline progress."""
        self.progress_bar.setValue(percent)
        self.status_indicator.set_status("busy", message)

    def _on_ocr_finished(self, regions: List[TextRegion]):
        """Handle OCR results."""
        self._current_regions = regions
        self.viewer.add_text_regions(regions)

    def _on_translation_finished(self, results: List[TranslationResult]):
        """Handle translation results."""
        self._current_translations = results

        # Update overlays with translations
        texts = [r.translated_text for r in results]
        self.viewer.clear_overlays()
        self.viewer.add_text_regions(self._current_regions, texts)

        # Update the translation panel
        self.translation_panel.set_translations(self._current_regions, results)

    def _on_pipeline_error(self, msg: str):
        """Handle pipeline error."""
        self.progress_bar.setVisible(False)
        self.status_indicator.set_status("error", f"Error: {msg}")
        QMessageBox.warning(self, "Processing Error", msg)

    def _on_pipeline_done(self):
        """Handle pipeline completion."""
        self.progress_bar.setVisible(False)
        count = len(self._current_translations)
        self.status_indicator.set_status("success", f"Translated {count} regions")
        self._update_actions()

    def _on_retranslate_one(self, index: int):
        """Retranslate a single region (on a background thread)."""
        if index < 0 or index >= len(self._current_regions):
            return
        region = self._current_regions[index]
        src = self.source_lang_combo.currentText()
        tgt = self.target_lang_combo.currentText()

        self.status_indicator.set_status("busy", f"Retranslating region {index + 1}...")
        worker = TranslationWorker(
            self.translator_manager, [region.text],
            source_lang=src, target_lang=tgt)
        worker.finished.connect(
            lambda results: self._on_retranslate_done(index, results))
        worker.error.connect(lambda e: self._on_retranslate_error(index, e))
        self._start_worker(worker)

    def _on_retranslate_done(self, index: int, results: List):
        """Handle a finished retranslation."""
        if not results:
            return
        result = results[0]
        if index < len(self._current_translations):
            self._current_translations[index] = result
        cell = self.translation_panel.table.item(index, 1)
        if cell is not None:
            cell.setText(result.translated_text)
        handle = self.viewer._overlay_items[index] if index < len(self.viewer._overlay_items) else None
        if handle is not None:
            handle.set_translation(result.translated_text)
        self.status_indicator.set_status("success", "Retranslation done")

    def _on_retranslate_error(self, index: int, msg: str):
        self.logger.error(f"Retranslate error: {msg}")
        self.status_indicator.set_status("error", f"Retranslate failed: {msg}")

    def _batch_translate(self, pages: List[Path]):
        """Translate all pages and export them."""
        output_dir = self.config.get("export.output_directory", "")
        if not output_dir:
            output_dir = QFileDialog.getExistingDirectory(
                self, "Select Output Directory")
            if not output_dir:
                return
            self.config.set("export.output_directory", output_dir)

        fmt = self.config.get("export.format", "png")
        quality = self.config.get("export.quality", 90)
        source_lang = self.source_lang_combo.currentText()
        target_lang = self.target_lang_combo.currentText()

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(pages))

        for i, page in enumerate(pages):
            self.progress_bar.setValue(i)
            self.status_indicator.set_status("busy", f"Translating {i + 1}/{len(pages)}: {page.name}")
            QApplication.processEvents()

            try:
                image = self.image_processor.load_image(page, auto_rotate=True)
                img = self.ocr_manager.preprocess_image(image) if self.config.get("ocr.preprocess", True) else image
                regions = self.ocr_manager.recognize(img)

                texts = [r.text for r in regions]
                results = self.translator_manager.translate_many(
                    texts, source_lang, target_lang)

                rendered = self.image_processor.render_translations(
                    image, regions, results,
                    inpaint=True,
                    bg_color=None,
                )

                out_path = Path(output_dir) / f"{page.stem}_translated.{fmt}"
                self.image_processor.save_image(rendered, out_path, fmt, quality)
                self.logger.info(f"Exported: {out_path}")
            except Exception as e:
                self.logger.error(f"Failed to process {page.name}: {e}")

        self.progress_bar.setVisible(False)
        self.status_indicator.set_status("success", f"Exported {len(pages)} pages to {output_dir}")
        QMessageBox.information(self, "Export Complete",
                                f"Exported {len(pages)} pages to:\n{output_dir}")

    # ----------------------------------------------------------- Overlay interaction

    def _on_region_selected(self, rect):
        """Handle a manually selected region."""
        if self._current_image is None:
            return

        bbox = (rect.x(), rect.y(), rect.width(), rect.height())
        # Clamp to image bounds
        bbox = (
            max(0, bbox[0]), max(0, bbox[1]),
            min(self._current_image.width - bbox[0], bbox[2]),
            min(self._current_image.height - bbox[1], bbox[3]),
        )

        # OCR just this region
        self.status_indicator.set_status("busy", "Recognizing selection...")
        x, y, w, h = bbox
        cropped = self._current_image.crop((x, y, x + w, y + h))

        worker = OCRWorker(self.ocr_manager, cropped,
                           self.config.get("ocr.preprocess", True))
        worker.regions_ready.connect(lambda regions: self._on_region_ocr(regions, bbox))
        self._current_worker = worker
        self._start_worker(worker)

    def _on_region_ocr(self, regions: List[TextRegion], bbox):
        """Handle OCR of a manually selected region."""
        x, y, _, _ = bbox
        if regions:
            for r in regions:
                # Offset to full image coordinates
                rx, ry, rw, rh = r.bbox
                r.bbox = (rx + x, ry + y, rw, rh)
                self._current_regions.append(r)
                self.viewer.add_text_region(r)
                self.status_indicator.set_status("success", f"Added: {r.text[:30]}")
        else:
            # No text detected, add an empty region for manual entry
            region = TextRegion(bbox=bbox, text="", confidence=1.0, language="unknown")
            self._current_regions.append(region)
            self.viewer.add_text_region(region)
            self.status_indicator.set_status("warning", "No text detected in selection")

        self.viewer.set_select_mode(False)
        self.select_region_action.setChecked(False)

    def _on_overlay_clicked(self, item):
        """Handle clicking on an overlay item."""
        try:
            idx = self.viewer._overlay_items.index(item)
        except ValueError:
            return
        # Select the corresponding row in the translation panel
        if idx < self.translation_panel.table.rowCount():
            self.translation_panel.table.selectRow(idx)

    def _on_toggle_select_mode(self):
        """Toggle manual region selection mode."""
        enabled = self.select_region_action.isChecked()
        self.viewer.set_select_mode(enabled)
        if enabled:
            self.status_indicator.set_status("idle", "Click and drag to select a region")
            self.statusbar.showMessage("Drag to select a text region. Press Esc to cancel.")

    def _on_clear_overlays(self):
        """Clear all overlays."""
        self.viewer.clear_overlays()
        self._current_regions = []
        self._current_translations = []
        self.translation_panel.clear()

    # -------------------------------------------------------------- View actions

    def _on_zoom_changed(self, level: float):
        """Handle zoom level changes."""
        self.zoom_label.setText(f"{int(level * 100)}%")

    def _on_toggle_bilingual(self):
        """Toggle bilingual view."""
        enabled = self.toggle_bilingual_action.isChecked()
        if enabled and self._current_image is not None:
            texts = [r.translated_text for r in self._current_translations]
            if self._current_regions and self._current_translations:
                rendered = self.image_processor.render_translations(
                    self._current_image, self._current_regions,
                    self._current_translations, inpaint=True
                )
                bilingual = self.image_processor.create_bilingual(
                    self._current_image, rendered, "side_by_side")
                self.viewer.load_image(self._pil_to_qimage(bilingual))
        else:
            if self._current_image is not None:
                self.viewer.load_image(self._pil_to_qimage(self._current_image))
                self._on_update_overlays()

    def _on_update_overlays(self):
        """Re-add overlays after a view refresh."""
        if self._current_regions:
            texts = [r.translated_text for r in self._current_translations] if self._current_translations else None
            self.viewer.add_text_regions(self._current_regions, texts)

    # ------------------------------------------------------------- Export actions

    def _on_export(self):
        """Export the current page."""
        if self._current_image is None:
            QMessageBox.information(self, "No Image", "Nothing to export.")
            return

        if not self._current_regions or not self._current_translations:
            QMessageBox.information(self, "No Translation",
                                    "Please translate the page first.")
            return

        fmt = self.config.get("export.format", "png")
        filter_str = {
            "png": "PNG Image (*.png)",
            "jpg": "JPEG Image (*.jpg)",
            "pdf": "PDF Document (*.pdf)",
        }.get(fmt, "All Files (*)")

        default_name = "translated.png"
        if self._current_index >= 0:
            default_name = f"{self._pages[self._current_index].stem}_translated.{fmt}"

        path, _ = QFileDialog.getSaveFileName(self, "Export Image", default_name, filter_str)
        if not path:
            return

        try:
            rendered = self.image_processor.render_translations(
                self._current_image,
                self._current_regions,
                self._current_translations,
                inpaint=True,
            )
            self.image_processor.save_image(
                rendered, Path(path), fmt, self.config.get("export.quality", 90))
            self.status_indicator.set_status("success", f"Exported to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    def _on_export_all(self):
        """Export all pages (batch translate + export)."""
        if not self._pages:
            QMessageBox.information(self, "No Images", "Nothing to export.")
            return
        self._batch_translate(list(self._pages))

    # ------------------------------------------------------------- Misc

    def _on_settings(self):
        """Open the settings dialog."""
        dialog = SettingsDialog(
            self.config, self.translator_manager, self.ocr_manager, self)
        if dialog.exec():
            # Reload engine combos
            self.ocr_engine_combo.clear()
            self.ocr_engine_combo.addItems(self.ocr_manager.get_available_engines())
            self.trans_engine_combo.clear()
            self.trans_engine_combo.addItems(self.translator_manager.get_available_engines())
            self.source_lang_combo.setCurrentText(
                self.config.get("translation.source_language", "auto"))
            self.target_lang_combo.setCurrentText(
                self.config.get("translation.target_language", "en"))

    def _on_ocr_engine_changed(self, name: str):
        """Handle OCR engine change."""
        self.ocr_manager.set_engine(name)
        self.status_indicator.set_status("idle", f"OCR engine: {name}")

    def _on_trans_engine_changed(self, name: str):
        """Handle translation engine change."""
        self.translator_manager.set_engine(name)
        self.status_indicator.set_status("idle", f"Translation engine: {name}")

    def _on_about(self):
        """Show the about dialog."""
        QMessageBox.about(
            self, "About Manga Translator",
            "<h3>Manga Translator 1.0.0</h3>"
            "<p>A modern PyQt6 application for translating manga and comics.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Multiple OCR engines (Tesseract, PaddleOCR, EasyOCR)</li>"
            "<li>Multiple translation engines (Google, DeepL, LibreTranslate)</li>"
            "<li>Interactive text region editing</li>"
            "<li>Batch processing and export</li>"
            "</ul>"
            "<p>Licensed under the MIT License.</p>"
        )

    def _update_actions(self):
        """Update the enabled state of actions."""
        has_image = self._current_image is not None
        has_pages = len(self._pages) > 0

        self.translate_action.setEnabled(has_image)
        self.select_region_action.setEnabled(has_image)
        self.clear_overlays_action.setEnabled(has_image)
        self.export_action.setEnabled(has_image)
        self.export_all_action.setEnabled(has_pages)
        self.close_action.setEnabled(has_pages)

        for action in (self.zoom_in_action, self.zoom_out_action,
                       self.fit_window_action, self.fit_width_action,
                       self.fit_height_action, self.reset_zoom_action,
                       self.toggle_bilingual_action):
            action.setEnabled(has_image)

        self.prev_page_action.setEnabled(self._current_index > 0)
        self.next_page_action.setEnabled(self._current_index < len(self._pages) - 1)

    @staticmethod
    def _pil_to_qimage(image: Image.Image) -> QImage:
        """Convert a PIL image to a QImage."""
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        return QImage(data, image.width, image.height,
                      QImage.Format.Format_RGBA8888).copy()

    # ------------------------------------------------------- Worker lifecycle

    def _start_worker(self, worker: QThread) -> QThread:
        """Start a worker and keep it alive until it finishes.

        Holds a strong reference in ``_active_workers`` and releases it only
        after the thread's ``finished`` signal fires, preventing the Qt
        "QThread: Destroyed while thread is still running" abort.
        """
        self._active_workers.add(worker)

        def _cleanup(w=worker):
            self._active_workers.discard(w)
            if self._current_worker is w:
                self._current_worker = None
            w.deleteLater()

        worker.finished.connect(_cleanup)
        worker.start()
        return worker

    def _stop_worker(self, worker: Optional[QThread], wait_ms: int = 2000):
        """Ask a worker to stop and wait for it to finish."""
        if worker is None or not worker.isRunning():
            return
        # Cooperative cancellation for our custom workers.
        cancel = getattr(worker, "cancel", None)
        if callable(cancel):
            cancel()
        worker.quit()
        if not worker.wait(wait_ms):
            # The worker's run() loop is not event-loop based; termination is
            # cooperative. Give it a final chance to observe the flag.
            worker.wait(wait_ms)

    # --------------------------------------------------------- Geometry persistence

    def _restore_geometry(self):
        """Restore window geometry from settings."""
        geometry = self.config.get("ui.window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self.config.get("ui.window_state")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        """Handle window close."""
        # Save geometry
        self.config.set("ui.window_geometry", self.saveGeometry())
        self.config.set("ui.window_state", self.saveState())
        self.config.save()

        # Stop every running worker and wait for it to terminate before the
        # objects are destroyed.
        for worker in list(self._active_workers):
            self._stop_worker(worker, 3000)
        self._active_workers.clear()
        self._current_worker = None

        super().closeEvent(event)


# Handle QApplication.aboutQt (it's a static method)
def _about_qt():
    QMessageBox.about(None, "About Qt", "Qt is a cross-platform application framework.")


if not hasattr(QApplication, "aboutQt"):
    QApplication.aboutQt = staticmethod(_about_qt)