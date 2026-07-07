"""Driving (inbound) ports.

These Protocols describe what the outside world can ask the
application core to do. The GTK panel, the CLI, and the clipboard
monitors all talk to the core exclusively through these interfaces —
they never import adapters or infrastructure.

The concrete implementations live in ``winclip.application.use_cases``.
"""

from __future__ import annotations

from typing import Protocol

from winclip.domain import ClipItem, Settings


class CapturesClipboard(Protocol):
    """Driven by clipboard monitors when the system clipboard changes."""

    def capture_text(self, text: str) -> ClipItem | None: ...

    def capture_image(self, png_data: bytes) -> ClipItem | None: ...


class QueriesHistory(Protocol):
    """Driven by any UI that displays the history."""

    def list_items(self) -> list[ClipItem]: ...

    def search(self, query: str) -> list[ClipItem]: ...


class ManagesHistory(Protocol):
    """Driven by UI actions: pin, delete, clear."""

    def toggle_pin(self, clip_id: str) -> ClipItem: ...

    def delete(self, clip_id: str) -> None: ...

    def clear(self) -> int: ...


class ActivatesClip(Protocol):
    """Driven by the UI when the user picks an item to paste."""

    def activate(self, clip_id: str) -> ActivationResult: ...


class ActivationResult(Protocol):
    copied: bool
    pasted: bool


class ManagesSettings(Protocol):
    def get_settings(self) -> Settings: ...

    def update_settings(self, settings: Settings) -> Settings: ...
