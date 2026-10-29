"""
Image viewer widget with zoom, pan, and translation overlay support.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem,
    QWidget, QMenu, QRubberBand, QApplication,
)
from PySide6.QtCore import (
    Qt, QRectF, QPointF, QRect, QSize, Signal, QPoint, QTimer,
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QBrush, QColor, QFont,
    QWheelEvent, QMouseEvent, QKeyEvent, QTransform, QFontMetrics,
)

from manga_translator.core.ocr import TextRegion
from manga_translator.core.translator import TranslationResult


class TextOverlayItem(QGraphicsRectItem):
    """Graphics item representing a text region with translation overlay."""

    def __init__(self, region: TextRegion, translation: Optional[str] = None):
        super().__init__()
        self.region = region
        self.translation = translation
        self._setup()

    def _setup(self):
        """Set up the overlay item."""
        x, y, w, h = self.region.bbox
        self.setRect(QRectF(0, 0, w, h))
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # Style
        self.setPen(QPen(QColor(0, 150, 255, 200), 2))
        self.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.setZValue(10)

    def paint(self, painter: QPainter, option, widget=None):
        """Custom paint for the overlay."""
        # Draw the base rect
        super().paint(painter, option, widget)

        # Draw translation text if available
        if self.translation:
            painter.save()
            font = QFont("Arial", 11)
            painter.setFont(font)

            rect = self.rect()
            # Draw translation on semi-transparent background
            bg = QColor(255, 255, 255, 230) if not self.isSelected() else QColor(230, 245, 255, 240)
            painter.setBrush(QBrush(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)

            # Draw text, wrapped
            painter.setPen(QPen(QColor(20, 20, 20)))
            text_rect = rect.adjusted(4, 4, -4, -4)
            flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
            painter.drawText(text_rect, flags, self.translation)
            painter.restore()

    def set_translation(self, translation: str):
        """Update the translation text."""
        self.translation = translation
        self.update()

    def itemChange(self, change, value):
        """Handle item changes."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update the region bbox
            pos = self.pos()
            self.region.bbox = (int(pos.x()), int(pos.y()),
                                int(self.rect().width()), int(self.rect().height()))
        return super().itemChange(change, value)


class ManualSelectionItem(QGraphicsRectItem):
    """A manually drawn selection region."""

    def __init__(self, rect: QRectF):
        super().__init__(rect)
        self.setPen(QPen(QColor(255, 100, 0, 220), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(255, 200, 100, 60)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setZValue(5)


class ImageViewer(QGraphicsView):
    """Image viewer with zoom, pan, and text overlay support."""

    region_selected = Signal(QRect)  # bbox in image coordinates
    region_clicked = Signal(object)  # TextOverlayItem
    zoom_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._overlay_items: List[TextOverlayItem] = []
        self._manual_selection: Optional[ManualSelectionItem] = None

        self._zoom_level = 1.0
        self._min_zoom = 0.05
        self._max_zoom = 20.0

        self._panning = False
        self._pan_start = QPoint()
        self._select_mode = False
        self._select_start = QPointF()
        self._rubber_band_origin = None

        self._setup_view()

    def _setup_view(self):
        """Configure the view."""
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))
        self.setMouseTracking(True)

    def load_image(self, image: QImage):
        """Load an image into the viewer."""
        self.clear_scene()

        pixmap = QPixmap.fromImage(image)
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._pixmap_item)

        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fit_to_window()

    def load_pixmap(self, pixmap: QPixmap):
        """Load a pixmap into the viewer."""
        self.clear_scene()

        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self._pixmap_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._scene.addItem(self._pixmap_item)

        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self.fit_to_window()

    def clear_scene(self):
        """Clear the scene."""
        self._scene.clear()
        self._pixmap_item = None
        self._overlay_items = []
        self._manual_selection = None

    def clear_overlays(self):
        """Remove all text overlays."""
        for item in self._overlay_items:
            if item.scene():
                self._scene.removeItem(item)
        self._overlay_items = []

        if self._manual_selection and self._manual_selection.scene():
            self._scene.removeItem(self._manual_selection)
        self._manual_selection = None

    def add_text_regions(self, regions: List[TextRegion], translations: Optional[List[str]] = None):
        """Add text region overlays to the scene."""
        self.clear_overlays()

        for i, region in enumerate(regions):
            translation = translations[i] if translations and i < len(translations) else None
            item = TextOverlayItem(region, translation)
            self._scene.addItem(item)
            self._overlay_items.append(item)

    def add_text_region(self, region: TextRegion, translation: Optional[str] = None) -> TextOverlayItem:
        """Add a single text region overlay."""
        item = TextOverlayItem(region, translation)
        self._scene.addItem(item)
        self._overlay_items.append(item)
        return item

    def get_overlay_regions(self) -> List[Tuple[TextRegion, Optional[str]]]:
        """Get all overlay regions with their translations."""
        return [(item.region, item.translation) for item in self._overlay_items]

    def update_translation(self, item: TextOverlayItem, translation: str):
        """Update translation for an overlay item."""
        item.set_translation(translation)

    # ---- Zoom operations ----

    def zoom_in(self, factor: float = 1.25):
        """Zoom in."""
        self._apply_zoom(factor)

    def zoom_out(self, factor: float = 0.8):
        """Zoom out."""
        self._apply_zoom(factor)

    def _apply_zoom(self, factor: float):
        """Apply a zoom factor."""
        new_zoom = self._zoom_level * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self._zoom_level = new_zoom
            self.scale(factor, factor)
            self.zoom_changed.emit(self._zoom_level)

    def set_zoom(self, level: float):
        """Set absolute zoom level."""
        level = max(self._min_zoom, min(self._max_zoom, level))
        factor = level / self._zoom_level
        self._zoom_level = level
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom_level)

    def get_zoom(self) -> float:
        """Get current zoom level."""
        return self._zoom_level

    def fit_to_window(self):
        """Fit image to window."""
        if not self._pixmap_item:
            return
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = self.transform().m11()
        self.zoom_changed.emit(self._zoom_level)

    def fit_width(self):
        """Fit image width to viewport."""
        if not self._pixmap_item:
            return
        rect = self._pixmap_item.boundingRect()
        if rect.width() > 0:
            factor = self.viewport().width() / rect.width()
            self.resetTransform()
            self.scale(factor, factor)
            self._zoom_level = factor
            self.zoom_changed.emit(self._zoom_level)

    def fit_height(self):
        """Fit image height to viewport."""
        if not self._pixmap_item:
            return
        rect = self._pixmap_item.boundingRect()
        if rect.height() > 0:
            factor = self.viewport().height() / rect.height()
            self.resetTransform()
            self.scale(factor, factor)
            self._zoom_level = factor
            self.zoom_changed.emit(self._zoom_level)

    def reset_zoom(self):
        """Reset zoom to 100%."""
        self.set_zoom(1.0)

    # ---- Selection mode ----

    def set_select_mode(self, enabled: bool):
        """Enable/disable manual region selection mode."""
        self._select_mode = enabled
        if enabled:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def is_select_mode(self) -> bool:
        """Check if selection mode is active."""
        return self._select_mode

    # ---- Event handlers ----

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in(1.15)
            else:
                self.zoom_out(0.87)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press."""
        if self._select_mode and event.button() == Qt.MouseButton.LeftButton:
            self._select_start = self.mapToScene(event.pos())
            if self._manual_selection and self._manual_selection.scene():
                self._scene.removeItem(self._manual_selection)
            self._manual_selection = ManualSelectionItem(QRectF(self._select_start, self._select_start))
            self._scene.addItem(self._manual_selection)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.LeftButton:
            # Check if an overlay item was clicked
            item = self.itemAt(event.pos())
            if isinstance(item, TextOverlayItem):
                self.region_clicked.emit(item)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move."""
        if self._select_mode and self._manual_selection and event.buttons() & Qt.MouseButton.LeftButton:
            current = self.mapToScene(event.pos())
            rect = QRectF(self._select_start, current).normalized()
            self._manual_selection.setRect(rect)
            event.accept()
            return
        elif self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release."""
        if self._select_mode and event.button() == Qt.MouseButton.LeftButton and self._manual_selection:
            rect = self._manual_selection.rect()
            if rect.width() > 5 and rect.height() > 5:
                bbox = QRect(
                    int(rect.x()), int(rect.y()),
                    int(rect.width()), int(rect.height())
                )
                self.region_selected.emit(bbox)
            event.accept()
            return
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            if self._select_mode:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press."""
        if event.key() == Qt.Key.Key_Escape and self._select_mode:
            self.set_select_mode(False)
            if self._manual_selection and self._manual_selection.scene():
                self._scene.removeItem(self._manual_selection)
            self._manual_selection = None
            event.accept()
            return
        super().keyPressEvent(event)