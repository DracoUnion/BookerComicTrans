"""
LLM-based OCR engine for Manga Translator.

Sends the page image to a vision model with the ``OCR_PMT`` prompt and parses
the structured JSON reply into :class:`~manga_translator.core.ocr.TextRegion`
objects. The model returns *relative* bboxes (0-1); these are scaled to pixels
via the image size so they line up with the rest of the UI.

Reuses:
- ``OCR_PMT`` from :mod:`manga_translator.core.llm_prompts`
- :class:`~manga_translator.core.llm_client.LLMClient` for the transport and
  ``parse_json`` for the (backtick-wrapped) JSON output.
"""

from __future__ import annotations

import io
from typing import List, Optional

from PIL import Image

from manga_translator.core.ocr import OCREngine, TextRegion
from manga_translator.core.llm_client import (
    LLMClient, LLMConfigError, get_vision_model, get_chat_model, parse_json,
)
from manga_translator.core.llm_prompts import OCR_PMT
from manga_translator.core.logger import get_logger

logger = get_logger("LLMOCREngine")


def _img_to_png(image: Image.Image) -> bytes:
    """Encode a PIL image as PNG bytes."""
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class LLMOCREngine(OCREngine):
    """OCR powered by a vision LLM."""

    def __init__(self, language: str = "jpn", model: Optional[str] = None):
        self.language = language
        # Prefer the vision model; fall back to the chat model so a
        # text-only endpoint can still be attempted.
        self.model = model or get_vision_model() or get_chat_model()
        self._client: Optional[LLMClient] = None
        self._init_failed = False

    # -- lazy -------------------------------------------------------------

    def _ensure_client(self) -> Optional[LLMClient]:
        if self._client is not None or self._init_failed:
            return self._client
        try:
            self._client = LLMClient(self.model, temp=0.1, retry=5)
        except LLMConfigError as ex:
            logger.warning(f"LLM OCR unavailable: {ex}")
            self._init_failed = True
        return self._client

    # -- interface --------------------------------------------------------

    @property
    def name(self) -> str:
        return "LLM (VLM)"

    @property
    def is_available(self) -> bool:
        from manga_translator.core.llm_client import is_configured
        return is_configured() and bool(self.model)

    def get_supported_languages(self) -> List[str]:
        # The VLM auto-detects; expose the same codes as the other engines.
        return ["jpn", "eng", "chi_sim", "chi_tra", "kor"]

    def recognize(self, image: Image.Image) -> List[TextRegion]:
        client = self._ensure_client()
        if client is None:
            return []

        w, h = image.size
        if w <= 0 or h <= 0:
            return []

        try:
            raw = client.ask_vlm(_img_to_png(image), OCR_PMT)
            data = parse_json(raw)
            if not isinstance(data, dict):
                raise ValueError("模型未返回 JSON 对象")
        except Exception as ex:
            logger.error(f"LLM OCR failed: {ex}")
            return []

        contents = data.get("contents") or []
        regions: List[TextRegion] = []

        for item in contents:
            try:
                typ = item.get("type", "paragraph")
                text = (item.get("markdown") or "").strip()
                if typ in ("header", "footer", "image"):
                    # Skip page chrome and decorative images.
                    continue
                if not text:
                    continue
                bbox = item.get("bbox") or []
                if len(bbox) != 4:
                    continue
                px = self._to_pixels(bbox, w, h)
                if px[2] <= 0 or px[3] <= 0:
                    continue
                regions.append(TextRegion(
                    bbox=px,
                    text=text,
                    confidence=1.0,
                    language=self.language,
                ))
            except Exception as ex:
                logger.debug(f"Skip malformed OCR block {item!r}: {ex}")

        logger.info(f"LLM OCR detected {len(regions)} regions")
        return regions

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _to_pixels(bbox: List[float], w: int, h: int):
        """Convert a relative [xmin,ymin,xmax,ymax] box to (x,y,w,h) pixels."""
        # Tolerate 0-1000 style coordinates as well as 0-1.
        if any(v > 1 for v in bbox):
            bbox = [v / 1000.0 for v in bbox]
        xmin, ymin, xmax, ymax = bbox
        x = int(round(max(0.0, min(1.0, xmin)) * w))
        y = int(round(max(0.0, min(1.0, ymin)) * h))
        x2 = int(round(max(0.0, min(1.0, xmax)) * w))
        y2 = int(round(max(0.0, min(1.0, ymax)) * h))
        return (x, y, max(1, x2 - x), max(1, y2 - y))
