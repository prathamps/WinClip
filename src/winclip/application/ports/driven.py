"""Driven (outbound) ports.

These are the interfaces the application core *requires* from the
outside world. Adapters on the right-hand side of the hexagon
(SQLite, wl-clipboard, GTK, …) implement them; the core only ever
sees these Protocols.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from winclip.domain import ClipItem, Settings


class HistoryRepository(Protocol):
    """Persistence for clipboard history."""

    def add(self, item: ClipItem) -> None: ...

    def get(self, clip_id: str) -> ClipItem | None: ...

    def find_by_hash(self, content_hash: str) -> ClipItem | None: ...

    def list_all(self) -> list[ClipItem]:
        """All items, no ordering guarantee (the domain sorts)."""
        ...

    def update(self, item: ClipItem) -> None: ...

    def remove(self, clip_id: str) -> None: ...

    def remove_many(self, clip_ids: list[str]) -> None: ...


class ClipboardWriter(Protocol):
    """Puts content onto the system clipboard."""

    def write_text(self, text: str) -> None: ...

    def write_image(self, png_data: bytes) -> None: ...


class PasteInjector(Protocol):
    """Synthesises a paste keystroke (Ctrl+V) into the focused window."""

    def paste(self) -> bool:
        """Attempt the paste. Returns False when injection is unavailable."""
        ...


class SettingsRepository(Protocol):
    """Persistence for user settings."""

    def load(self) -> Settings: ...

    def save(self, settings: Settings) -> None: ...


class CommandHistorySource(Protocol):
    """Access to the user's shell command history."""

    def recent_commands(self) -> list[str]:
        """Raw command lines, oldest first. Empty when unavailable."""
        ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new_id(self) -> str: ...
