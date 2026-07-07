"""Ports: the boundary of the application core.

``driven``  — interfaces the core needs implemented (repository,
              clipboard writer, paste injector, clock, …).
``driving`` — interfaces through which the core is invoked (capture,
              query, manage, activate).
"""

from .driven import (
    ClipboardWriter,
    Clock,
    HistoryRepository,
    IdGenerator,
    PasteInjector,
    SettingsRepository,
)
from .driving import (
    ActivatesClip,
    CapturesClipboard,
    ManagesHistory,
    ManagesSettings,
    QueriesHistory,
)

__all__ = [
    "ActivatesClip",
    "CapturesClipboard",
    "Clock",
    "ClipboardWriter",
    "HistoryRepository",
    "IdGenerator",
    "ManagesHistory",
    "ManagesSettings",
    "PasteInjector",
    "QueriesHistory",
    "SettingsRepository",
]
