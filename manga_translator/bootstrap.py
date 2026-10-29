"""
Application bootstrap.

Assembles the zero-Qt service graph into an :class:`AppContext` and returns
it. The UI layer never constructs managers itself — it only receives the
context and a Qt bridge over ``ctx.tasks`` events.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from manga_translator.common.context import AppContext
from manga_translator.common.events import EventHub
from manga_translator.core.config import ConfigManager
from manga_translator.core.logger import setup_logger
from manga_translator.core.ocr import OCRManager
from manga_translator.core.translator import TranslatorManager
from manga_translator.services.facade import ServiceFacade
from manga_translator.tasks import TaskManager


def build_context(
    *,
    config_file: Optional[str | Path] = None,
    max_workers: int = 4,
    extras: Optional[dict[str, Any]] = None,
) -> AppContext:
    """Assemble services and return an :class:`AppContext`."""
    logger = setup_logger("MangaTranslator")
    logger.info("bootstrap: assembling AppContext")
    logger.debug("bootstrap: config file = %s", config_file)

    config = ConfigManager(str(config_file) if config_file else None)
    events = EventHub()
    tasks = TaskManager(max_workers=max_workers, events=events)
    ocr = OCRManager(config)
    translator = TranslatorManager(config)
    services = ServiceFacade(
        config=config,
        ocr=ocr,
        translator=translator,
        events=events,
        tasks=tasks,
    )

    ctx = AppContext(
        config=config,
        events=events,
        tasks=tasks,
        services=services,
        extras=extras or {},
    )
    # Convenience alias so pages can reach the managers that predate the
    # facade (kept for backward compatibility during the transition).
    ctx.extras.setdefault("ocr_manager", ocr)
    ctx.extras.setdefault("translator_manager", translator)
    return ctx