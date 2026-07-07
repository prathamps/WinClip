"""Core domain models for WinClip.

This module is the heart of the hexagon: it has no dependencies on
anything outside the standard library and knows nothing about GTK,
SQLite, Wayland, or any other technology.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum


class ContentKind(str, Enum):
    """The kind of content a clipboard item holds."""

    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True)
class ClipItem:
    """A single entry in the clipboard history.

    Items are immutable value objects; state changes produce new
    instances (see :meth:`pinned_as` and :meth:`touched`).
    """

    id: str
    kind: ContentKind
    content_hash: str
    created_at: datetime
    last_used_at: datetime
    pinned: bool = False
    text: str | None = None
    image: bytes | None = field(default=None, repr=False)

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(b"text\x00" + text.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_image(data: bytes) -> str:
        return hashlib.sha256(b"image\x00" + data).hexdigest()

    @classmethod
    def from_text(
        cls, item_id: str, text: str, now: datetime, pinned: bool = False
    ) -> ClipItem:
        return cls(
            id=item_id,
            kind=ContentKind.TEXT,
            content_hash=cls.hash_text(text),
            created_at=now,
            last_used_at=now,
            pinned=pinned,
            text=text,
        )

    @classmethod
    def from_image(
        cls, item_id: str, data: bytes, now: datetime, pinned: bool = False
    ) -> ClipItem:
        return cls(
            id=item_id,
            kind=ContentKind.IMAGE,
            content_hash=cls.hash_image(data),
            created_at=now,
            last_used_at=now,
            pinned=pinned,
            image=data,
        )

    @property
    def size_bytes(self) -> int:
        if self.kind is ContentKind.TEXT:
            return len((self.text or "").encode("utf-8"))
        return len(self.image or b"")

    def preview(self, max_chars: int = 200) -> str:
        """A short, single-paragraph description suitable for lists."""
        if self.kind is ContentKind.IMAGE:
            kib = max(1, self.size_bytes // 1024)
            return f"[Image, {kib} KiB]"
        text = (self.text or "").strip()
        collapsed = " ".join(text.split())
        if len(collapsed) > max_chars:
            return collapsed[: max_chars - 1] + "…"
        return collapsed

    def pinned_as(self, pinned: bool) -> ClipItem:
        return replace(self, pinned=pinned)

    def touched(self, now: datetime) -> ClipItem:
        """Mark the item as used, moving it to the top of the history."""
        return replace(self, last_used_at=now)

    def matches(self, query: str) -> bool:
        """Case-insensitive substring search over textual content."""
        if not query:
            return True
        if self.kind is ContentKind.TEXT and self.text:
            return query.lower() in self.text.lower()
        return False


DEFAULT_MAX_ITEMS = 50
DEFAULT_MAX_ITEM_BYTES = 4 * 1024 * 1024  # same per-item cap Windows uses


@dataclass(frozen=True)
class Settings:
    """User-tunable behaviour. Validated on construction."""

    max_items: int = DEFAULT_MAX_ITEMS
    max_item_bytes: int = DEFAULT_MAX_ITEM_BYTES
    capture_images: bool = True
    auto_paste: bool = True
    paste_tool: str = "auto"  # auto | none | ydotool | wtype | xdotool

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise ValueError("max_items must be at least 1")
        if self.max_item_bytes < 1:
            raise ValueError("max_item_bytes must be at least 1")
        if self.paste_tool not in ("auto", "none", "ydotool", "wtype", "xdotool"):
            raise ValueError(f"unknown paste_tool: {self.paste_tool!r}")
