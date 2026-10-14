"""
Background worker threads for Manga Translator.
"""

from typing import List, Optional
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import QImage

from PIL import Image

from manga_translator.core.ocr import OCRManager, TextRegion
from manga_translator.core.translator import TranslatorManager, TranslationResult
from manga_translator.core.logger import get_logger


class OCRWorker(QThread):
    """Worker thread for OCR processing.

    Note: the result signal is named ``regions_ready`` rather than
    ``finished`` because ``QThread`` already defines a ``finished`` signal;
    shadowing it breaks Qt's internal thread teardown.
    """

    regions_ready = pyqtSignal(list)  # List[TextRegion]
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, ocr_manager: OCRManager, image: Image.Image, preprocess: bool = True):
        super().__init__()
        self.ocr_manager = ocr_manager
        self.image = image
        self.preprocess = preprocess
        self.logger = get_logger("OCRWorker")

    def run(self):
        try:
            self.progress.emit(10)
            img = self.image
            if self.preprocess:
                img = self.ocr_manager.preprocess_image(img)
            self.progress.emit(40)

            regions = self.ocr_manager.recognize(img)
            self.progress.emit(100)
            self.regions_ready.emit(regions)
        except Exception as e:
            self.logger.error(f"OCR error: {e}")
            self.error.emit(str(e))


class TranslationWorker(QThread):
    """Worker thread for translation processing."""

    translations_ready = pyqtSignal(list)  # List[TranslationResult]
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, translator_manager: TranslatorManager, texts: List[str],
                 source_lang: str = None, target_lang: str = None):
        super().__init__()
        self.translator_manager = translator_manager
        self.texts = texts
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.logger = get_logger("TranslationWorker")
        self._cancelled = False

    def run(self):
        try:
            results = []
            total = len(self.texts)
            for i, text in enumerate(self.texts):
                if self._cancelled:
                    break
                result = self.translator_manager.translate(
                    text, self.source_lang, self.target_lang
                )
                results.append(result)
                self.progress.emit(i + 1, total)
            self.translations_ready.emit(results)
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the translation."""
        self._cancelled = True


class PipelineWorker(QThread):
    """Worker that runs the full OCR + translation pipeline."""

    ocr_finished = pyqtSignal(list)  # List[TextRegion]
    translation_finished = pyqtSignal(list)  # List[TranslationResult]
    progress = pyqtSignal(int, str)  # percent, message
    error = pyqtSignal(str)
    finished_all = pyqtSignal()

    def __init__(self, ocr_manager: OCRManager, translator_manager: TranslatorManager,
                 image: Image.Image, source_lang: str = None, target_lang: str = None,
                 preprocess: bool = True):
        super().__init__()
        self.ocr_manager = ocr_manager
        self.translator_manager = translator_manager
        self.image = image
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.preprocess = preprocess
        self.logger = get_logger("PipelineWorker")
        self._cancelled = False

    def run(self):
        try:
            # OCR stage
            self.progress.emit(5, "Preprocessing image...")
            img = self.image
            if self.preprocess:
                img = self.ocr_manager.preprocess_image(img)

            self.progress.emit(20, "Detecting text...")
            regions = self.ocr_manager.recognize(img)

            if self._cancelled:
                return

            self.ocr_finished.emit(regions)
            self.progress.emit(50, f"Detected {len(regions)} regions. Translating...")

            if self._cancelled:
                return

            # Translation stage — batch the whole page into as few LLM calls
            # as possible (the LLM engine merges everything into one JSON
            # request, see TranslatorManager.translate_many).
            texts = [r.text for r in regions]
            results = self.translator_manager.translate_many(
                texts, self.source_lang, self.target_lang
            )

            if self._cancelled:
                return

            self.translation_finished.emit(results)
            self.progress.emit(100, "Done")
            self.finished_all.emit()
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the pipeline."""
        self._cancelled = True


class ImageLoadWorker(QThread):
    """Worker for loading large images off the UI thread.

    Uses ``loaded`` rather than ``finished`` for the result so as not to
    shadow ``QThread.finished``.
    """

    loaded = pyqtSignal(object)  # PIL.Image.Image
    error = pyqtSignal(str)
    thumbnail_ready = pyqtSignal(object)  # QImage

    def __init__(self, path: Path, make_thumbnail: bool = True):
        super().__init__()
        self.path = path
        self.make_thumbnail = make_thumbnail

    def run(self):
        try:
            image = Image.open(self.path)
            image.load()

            if self.make_thumbnail:
                thumb = image.copy()
                thumb.thumbnail((160, 220))
                if thumb.mode != "RGBA":
                    thumb = thumb.convert("RGBA")
                data = thumb.tobytes("raw", "RGBA")
                qimage = QImage(data, thumb.width, thumb.height,
                                QImage.Format.Format_RGBA8888).copy()
                self.thumbnail_ready.emit(qimage)

            self.loaded.emit(image)
        except Exception as e:
            self.error.emit(str(e))