"""
OCR Manager for Manga Translator.
Supports multiple OCR engines.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from manga_translator.core.config import ConfigManager
from manga_translator.core.logger import get_logger


@dataclass
class TextRegion:
    """Represents a detected text region in an image."""
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    text: str
    confidence: float
    language: str = "unknown"


class OCREngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def recognize(self, image: Image.Image) -> List[TextRegion]:
        """Recognize text in image."""
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Return supported language codes."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return engine name."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available."""
        pass


class TesseractEngine(OCREngine):
    """Tesseract OCR engine."""

    def __init__(self, tesseract_path: str = "", language: str = "jpn"):
        self.tesseract_path = tesseract_path
        self.language = language
        self._tesseract = None
        self._init_tesseract()

    def _init_tesseract(self):
        """Initialize Tesseract."""
        try:
            import pytesseract
            if self.tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            # Test if tesseract is available
            pytesseract.get_tesseract_version()
            self._tesseract = pytesseract
        except Exception as e:
            self._tesseract = None

    def recognize(self, image: Image.Image) -> List[TextRegion]:
        if not self._tesseract:
            return []

        try:
            # Get detailed data including bounding boxes
            data = self._tesseract.image_to_data(
                image,
                lang=self.language,
                output_type=self._tesseract.Output.DICT
            )

            regions = []
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                if int(data['conf'][i]) > 0:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    text = data['text'][i].strip()
                    if text:
                        regions.append(TextRegion(
                            bbox=(x, y, w, h),
                            text=text,
                            confidence=float(data['conf'][i]) / 100.0,
                            language=self.language
                        ))
            return regions
        except Exception as e:
            return []

    def get_supported_languages(self) -> List[str]:
        if not self._tesseract:
            return []
        try:
            return self._tesseract.get_languages(config='')
        except Exception:
            return ["jpn", "eng", "chi_sim", "chi_tra", "kor"]

    @property
    def name(self) -> str:
        return "Tesseract"

    @property
    def is_available(self) -> bool:
        return self._tesseract is not None


class PaddleOCREngine(OCREngine):
    """PaddleOCR engine (high accuracy for Asian languages).

    Initialization is lazy: the (heavy) model is only loaded the first time
    ``recognize`` is called, so merely listing the engine does not block.
    """

    def __init__(self, language: str = "japan", use_gpu: bool = False):
        self.language = language
        self.use_gpu = use_gpu
        self._ocr = None
        self._init_failed = False

    def _ensure_initialized(self):
        """Initialize PaddleOCR on first use."""
        if self._ocr is not None or self._init_failed:
            return
        try:
            from paddleocr import PaddleOCR
            lang_map = {
                "jpn": "japan",
                "ja": "japan",
                "chi_sim": "ch",
                "chi_tra": "chinese_cht",
                "kor": "korean",
                "ko": "korean",
                "eng": "en",
                "en": "en",
            }
            paddle_lang = lang_map.get(self.language, "japan")
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=paddle_lang,
                use_gpu=self.use_gpu,
                show_log=False
            )
        except Exception:
            self._init_failed = True
            self._ocr = None

    @property
    def is_available(self) -> bool:
        """Check availability by import test (does not load models)."""
        try:
            import paddleocr  # noqa: F401
            return True
        except Exception:
            return False

    def recognize(self, image: Image.Image) -> List[TextRegion]:
        self._ensure_initialized()
        if not self._ocr:
            return []

        try:
            # Convert PIL to numpy
            img_array = np.array(image.convert("RGB"))
            result = self._ocr.ocr(img_array, cls=True)

            regions = []
            if result and result[0]:
                for line in result[0]:
                    bbox, (text, confidence) = line
                    # Convert bbox to x, y, w, h
                    xs = [p[0] for p in bbox]
                    ys = [p[1] for p in bbox]
                    x, y = int(min(xs)), int(min(ys))
                    w, h = int(max(xs) - min(xs)), int(max(ys) - min(ys))

                    regions.append(TextRegion(
                        bbox=(x, y, w, h),
                        text=text,
                        confidence=confidence,
                        language=self.language
                    ))
            return regions
        except Exception:
            return []

    def get_supported_languages(self) -> List[str]:
        return ["japan", "ch", "chinese_cht", "korean", "en", "fr", "de", "es", "ru"]

    @property
    def name(self) -> str:
        return "PaddleOCR"


class EasyOCREngine(OCREngine):
    """EasyOCR engine (good for multiple languages).

    Initialization is lazy: models are only downloaded/loaded the first time
    ``recognize`` is called, so listing the engine does not block startup.
    """

    def __init__(self, languages: List[str] = None, use_gpu: bool = False):
        self.languages = languages or ["ja", "en"]
        self.use_gpu = use_gpu
        self._reader = None
        self._init_failed = False

    def _ensure_initialized(self):
        """Initialize EasyOCR on first use."""
        if self._reader is not None or self._init_failed:
            return
        try:
            import easyocr
            self._reader = easyocr.Reader(self.languages, gpu=self.use_gpu)
        except Exception:
            self._init_failed = True
            self._reader = None

    @property
    def is_available(self) -> bool:
        """Check availability by import test (does not load models)."""
        try:
            import easyocr  # noqa: F401
            return True
        except Exception:
            return False

    def recognize(self, image: Image.Image) -> List[TextRegion]:
        self._ensure_initialized()
        if not self._reader:
            return []

        try:
            img_array = np.array(image.convert("RGB"))
            results = self._reader.readtext(img_array)

            regions = []
            for bbox, text, confidence in results:
                # Convert bbox to x, y, w, h
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                x, y = int(min(xs)), int(min(ys))
                w, h = int(max(xs) - min(xs)), int(max(ys) - min(ys))

                regions.append(TextRegion(
                    bbox=(x, y, w, h),
                    text=text,
                    confidence=confidence,
                    language=self.languages[0] if self.languages else "unknown"
                ))
            return regions
        except Exception:
            return []

    def get_supported_languages(self) -> List[str]:
        return [
            "en", "ja", "ch_sim", "ch_tra", "ko", "fr", "de", "es",
            "ru", "ar", "hi", "th", "vi", "it", "pt", "nl"
        ]

    @property
    def name(self) -> str:
        return "EasyOCR"


class MockOCREngine(OCREngine):
    """Mock OCR engine for testing."""

    def recognize(self, image: Image.Image) -> List[TextRegion]:
        # Return a mock text region
        w, h = image.size
        return [
            TextRegion(
                bbox=(10, 10, w - 20, 50),
                text="サンプルテキスト (Sample Text)",
                confidence=0.95,
                language="jpn"
            ),
            TextRegion(
                bbox=(10, 70, w - 20, 50),
                text="これはテストです。",
                confidence=0.90,
                language="jpn"
            ),
        ]

    def get_supported_languages(self) -> List[str]:
        return ["jpn", "eng", "chi_sim", "kor"]

    @property
    def name(self) -> str:
        return "Mock OCR"

    @property
    def is_available(self) -> bool:
        return True


class OCRManager:
    """Manages OCR engines and operations."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = get_logger("OCRManager")
        self.engines: Dict[str, OCREngine] = {}
        self.current_engine: Optional[OCREngine] = None
        self._init_engines()

    def _init_engines(self):
        """Initialize available OCR engines."""
        # Always available mock engine
        self.engines["mock"] = MockOCREngine()

        # Tesseract
        tesseract_path = self.config.get("ocr.tesseract_path", "")
        language = self.config.get("ocr.language", "jpn")
        self.engines["tesseract"] = TesseractEngine(tesseract_path, language)

        # PaddleOCR (if available)
        try:
            self.engines["paddleocr"] = PaddleOCREngine(language)
        except Exception:
            pass

        # EasyOCR (if available)
        easyocr_lang = "ja" if language in ("jpn", "ja") else "en"
        try:
            self.engines["easyocr"] = EasyOCREngine([easyocr_lang, "en"])
        except Exception:
            pass

        # Set current engine
        engine_name = self.config.get("ocr.engine", "tesseract")
        self.set_engine(engine_name)

    def set_engine(self, engine_name: str) -> bool:
        """Set the active OCR engine."""
        if engine_name in self.engines and self.engines[engine_name].is_available:
            self.current_engine = self.engines[engine_name]
            self.config.set("ocr.engine", engine_name)
            self.logger.info(f"OCR engine set to: {engine_name}")
            return True
        elif engine_name == "mock":
            self.current_engine = self.engines["mock"]
            self.config.set("ocr.engine", "mock")
            return True
        return False

    def get_available_engines(self) -> List[str]:
        """Get list of available engine names."""
        return [name for name, engine in self.engines.items() if engine.is_available]

    def get_current_engine(self) -> Optional[OCREngine]:
        """Get the current OCR engine."""
        return self.current_engine

    def recognize(self, image: Image.Image) -> List[TextRegion]:
        """Recognize text in image using current engine."""
        if not self.current_engine:
            self.logger.warning("No OCR engine available, using mock")
            self.current_engine = self.engines.get("mock")

        if not self.current_engine:
            return []

        self.logger.debug(f"Recognizing text with {self.current_engine.name}")
        regions = self.current_engine.recognize(image)

        # Filter by confidence threshold
        threshold = self.config.get("ocr.confidence_threshold", 60) / 100.0
        filtered = [r for r in regions if r.confidence >= threshold]

        self.logger.info(f"Detected {len(filtered)} text regions (from {len(regions)} total)")
        return filtered

    def recognize_region(self, image: Image.Image, bbox: Tuple[int, int, int, int]) -> Optional[TextRegion]:
        """Recognize text in a specific region."""
        x, y, w, h = bbox
        cropped = image.crop((x, y, x + w, y + h))
        regions = self.recognize(cropped)
        if regions:
            # Adjust bbox to original coordinates
            region = regions[0]
            region.bbox = (x + region.bbox[0], y + region.bbox[1], region.bbox[2], region.bbox[3])
            return region
        return None

    def set_language(self, language: str):
        """Set OCR language."""
        self.config.set("ocr.language", language)
        # Reinitialize current engine with new language
        engine_name = self.config.get("ocr.engine", "tesseract")
        if engine_name == "tesseract":
            tesseract_path = self.config.get("ocr.tesseract_path", "")
            self.engines["tesseract"] = TesseractEngine(tesseract_path, language)
        elif engine_name == "paddleocr":
            self.engines["paddleocr"] = PaddleOCREngine(language)
        elif engine_name == "easyocr":
            self.engines["easyocr"] = EasyOCREngine([language, "en"])
        self.set_engine(engine_name)

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results."""
        if not self.config.get("ocr.preprocess", True):
            return image

        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')

        # Enhance contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        # Sharpen
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        return image