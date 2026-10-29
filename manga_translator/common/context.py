"""
Application context (zero Qt).

``AppContext`` is assembled by :func:`manga_translator.bootstrap.build_context`
and handed to the UI layer. The UI only ever talks to these well-known
handles, never importing Qt into services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from manga_translator.common.events import EventHub

if TYPE_CHECKING:
    from manga_translator.core.config import ConfigManager
    from manga_translator.services.facade import ServiceFacade
    from manga_translator.tasks import TaskManager


@dataclass
class AppContext:
    """Bundle of run-time services injected at bootstrap time."""

    config: "ConfigManager"
    events: EventHub
    tasks: "TaskManager"
    services: "ServiceFacade"
    extras: dict[str, Any] = field(default_factory=dict)

    def extra(self, key: str, default: Any = None) -> Any:
        """Read an optional bootstrap-injected dependency."""
        return self.extras.get(key, default)