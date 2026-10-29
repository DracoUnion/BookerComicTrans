"""
Custom widgets for Manga Translator UI.
"""

from typing import List, Optional, Dict
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QTextEdit, QPushButton, QScrollArea, QFrame,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QComboBox, QLineEdit, QAbstractItemView, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QPixmap, QIcon, QColor, QFont, QPainter, QBrush

from manga_translator.core.ocr import TextRegion
from manga_translator.core.translator import TranslationResult


class PageListWidget(QWidget):
    """Widget for displaying a list of pages/thumbnails."""

    page_selected = Signal(int)  # page index
    page_removed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: List[Path] = []
        self._thumbnails: Dict[int, QPixmap] = {}
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QLabel("Pages")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # List
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(80, 110))
        self.list_widget.setSpacing(2)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

    def _on_selection_changed(self, row: int):
        """Handle selection change."""
        if row >= 0:
            self.page_selected.emit(row)

    def set_pages(self, pages: List[Path]):
        """Set the list of pages."""
        self._pages = pages
        self.list_widget.clear()

        for i, page in enumerate(pages):
            item = QListWidgetItem()
            item.setText(f"{i + 1}. {page.name}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_widget.addItem(item)

    def set_thumbnail(self, index: int, pixmap: QPixmap):
        """Set a thumbnail for a page."""
        if index < 0 or index >= self.list_widget.count():
            return

        self._thumbnails[index] = pixmap
        scaled = pixmap.scaled(
            80, 110,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        item = self.list_widget.item(index)
        if item:
            item.setIcon(QIcon(scaled))

    def get_current_index(self) -> int:
        """Get current selected index."""
        return self.list_widget.currentRow()

    def set_current_index(self, index: int):
        """Set current selected index."""
        if 0 <= index < self.list_widget.count():
            self.list_widget.setCurrentRow(index)

    def count(self) -> int:
        """Get number of pages."""
        return self.list_widget.count()

    def remove_page(self, index: int):
        """Remove a page."""
        if 0 <= index < self.list_widget.count():
            self.list_widget.takeItem(index)
            if index < len(self._pages):
                self._pages.pop(index)
            self.page_removed.emit(index)


class TranslationPanel(QWidget):
    """Panel showing translations for the current page."""

    translation_edited = Signal(int, str)  # index, new text
    retranslate_requested = Signal(int)  # index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QLabel("Translations")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Original", "Translation", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 40)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        self.retranslate_btn = QPushButton("Retranslate All")
        self.retranslate_btn.clicked.connect(self._on_retranslate_all)
        button_layout.addWidget(self.retranslate_btn)

        self.export_btn = QPushButton("Export...")
        button_layout.addWidget(self.export_btn)

        layout.addLayout(button_layout)

    def set_translations(self, regions: List[TextRegion], translations: List[TranslationResult]):
        """Populate the table with translations."""
        self.table.setRowCount(len(regions))

        for i, (region, trans) in enumerate(zip(regions, translations)):
            # Original text
            orig_item = QTableWidgetItem(region.text)
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, orig_item)

            # Translated text (editable)
            trans_item = QTableWidgetItem(trans.translated_text)
            trans_item.setData(Qt.ItemDataRole.UserRole, i)
            self.table.setItem(i, 1, trans_item)

            # Retranslate button
            btn = QPushButton("⟳")
            btn.setFixedWidth(32)
            btn.clicked.connect(lambda checked, idx=i: self.retranslate_requested.emit(idx))
            self.table.setCellWidget(i, 2, btn)

        self.table.resizeRowsToContents()

    def get_translation(self, index: int) -> Optional[str]:
        """Get translation text at index."""
        item = self.table.item(index, 1)
        return item.text() if item else None

    def _on_retranslate_all(self):
        """Request retranslation of all entries."""
        for i in range(self.table.rowCount()):
            self.retranslate_requested.emit(i)

    def clear(self):
        """Clear the table."""
        self.table.setRowCount(0)


class StatusIndicator(QWidget):
    """A small status indicator with icon and text."""

    def __init__(self, text: str = "", status: str = "idle", parent=None):
        super().__init__(parent)
        self._status = status
        self._text = text
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        self.indicator = QLabel()
        self.indicator.setFixedSize(10, 10)
        layout.addWidget(self.indicator)

        self.label = QLabel(self._text)
        layout.addWidget(self.label)

        self._update_indicator()

    def set_status(self, status: str, text: Optional[str] = None):
        """Set the status."""
        self._status = status
        if text is not None:
            self._text = text
            self.label.setText(text)
        self._update_indicator()

    def _update_indicator(self):
        """Update the indicator color."""
        colors = {
            "idle": "#888888",
            "busy": "#FFA500",
            "success": "#4CAF50",
            "error": "#F44336",
            "warning": "#FFC107",
        }
        color = colors.get(self._status, "#888888")
        self.indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
        )


class TranslationOverlay(QWidget):
    """Floating overlay widget for showing translation near cursor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(400)
        self.label.setStyleSheet(
            """
            background-color: rgba(255, 255, 255, 240);
            color: #202020;
            border: 1px solid #888;
            border-radius: 4px;
            padding: 6px;
            """
        )
        layout.addWidget(self.label)

    def show_translation(self, text: str, pos):
        """Show translation at the given position."""
        self.label.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()

    def hide_overlay(self):
        """Hide the overlay."""
        self.hide()


class ImageDropArea(QLabel):
    """A drop area for images."""

    files_dropped = Signal(list)  # list of paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Drop manga/comic images here\nor use File → Open")
        self.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #888888;
                border-radius: 8px;
                padding: 40px;
                color: #888888;
                font-size: 14px;
                background-color: transparent;
            }
            """
        )

    def dragEnterEvent(self, event):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop."""
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()


class RegionListWidget(QWidget):
    """List of detected text regions."""

    region_selected = Signal(int)
    region_deleted = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_selection)
        layout.addWidget(self.list)

    def _on_selection(self, row: int):
        """Handle selection."""
        if row >= 0:
            self.region_selected.emit(row)

    def set_regions(self, regions: List[TextRegion]):
        """Set the regions."""
        self.list.clear()
        for i, region in enumerate(regions):
            item = QListWidgetItem(f"{i + 1}. {region.text[:40]}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)

    def clear(self):
        """Clear the list."""
        self.list.clear()