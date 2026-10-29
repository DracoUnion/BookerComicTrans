"""
Service layer: a zero-Qt ``ServiceFacade`` as the single entry for callers
above (UI / tests). Wraps the OCR / translation / rendering managers plus
the background :class:`TaskManager`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from manga_translator.common.events import EventHub
from manga_translator.tasks import Task, TaskManager, TaskCancelled

if TYPE_CHECKING:
    from manga_translator.core.config import ConfigManager
    from manga_translator.core.ocr import OCRManager, TextRegion
    from manga_translator.core.translator import TranslatorManager, TranslationResult


class ServiceFacade:
    """UI-facing facade; no Qt imports."""

    def __init__(
        self,
        *,
        config: "ConfigManager",
        ocr: "OCRManager",
        translator: "TranslatorManager",
        events: EventHub,
        tasks: TaskManager,
    ) -> None:
        self.config = config
        self.ocr = ocr
        self.translator = translator
        self.events = events
        self.tasks = tasks

    # -- OCR ------------------------------------------------------------- #

    def recognize(self, image, preprocess: bool = True) -> List["TextRegion"]:
        """Synchronous OCR (used by region selection)."""
        img = image
        if preprocess:
            img = self.ocr.preprocess_image(image)
        return self.ocr.recognize(img)

    # -- Translation ----------------------------------------------------- #

    def translate_many(
        self,
        texts: List[str],
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> List["TranslationResult"]:
        return self.translator.translate_many(texts, source_lang, target_lang)

    def translate(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> "TranslationResult":
        return self.translator.translate(text, source_lang, target_lang)

    # -- Background tasks ------------------------------------------------ #

    def submit_pipeline(
        self,
        image,
        *,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        preprocess: bool = True,
        label: str = "pipeline",
    ) -> Task:
        """Run OCR+translation on a page in the background."""

        def _run(*, cancel_event, **_: Any) -> dict[str, Any]:
            if cancel_event.is_set():
                raise TaskCancelled()
            img = image
            if preprocess:
                img = self.ocr.preprocess_image(image)
            regions = self.ocr.recognize(img)
            texts = [r.text for r in regions]
            results = self.translator.translate_many(texts, source_lang, target_lang)
            return {"regions": regions, "results": results}

        return self.tasks.submit(_run, label=label)

    def submit_load_image(self, path, label: str = "load-image") -> Task:
        """Load an image file off the UI thread."""

        def _run(*, cancel_event, **_: Any) -> Any:
            from PIL import Image

            if cancel_event.is_set():
                raise TaskCancelled()
            image = Image.open(path)
            image.load()
            return image

        return self.tasks.submit(_run, label=label)