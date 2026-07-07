"""History policy: the business rules of the clipboard history.

These rules intentionally mirror the Windows clipboard (Win+V)
behaviour:

* Re-copying existing content moves it to the top instead of
  duplicating it.
* The history keeps at most ``max_items`` unpinned entries; the oldest
  unpinned entries are evicted first.
* Pinned entries are never evicted and survive "Clear all".
* Oversized items are never captured.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import ClipItem, Settings


class HistoryPolicy:
    """Pure decision logic — no I/O, trivially unit-testable."""

    def is_capturable(self, size_bytes: int, is_image: bool, settings: Settings) -> bool:
        if size_bytes == 0:
            return False
        if size_bytes > settings.max_item_bytes:
            return False
        if is_image and not settings.capture_images:  # noqa: SIM103 — guard style
            return False
        return True

    def eviction_victims(
        self, items: Sequence[ClipItem], settings: Settings
    ) -> list[ClipItem]:
        """Unpinned items that exceed the history cap, oldest-used first."""
        unpinned = sorted(
            (i for i in items if not i.pinned),
            key=lambda i: i.last_used_at,
            reverse=True,
        )
        return unpinned[settings.max_items :]

    def clearable(self, items: Sequence[ClipItem]) -> list[ClipItem]:
        """Items removed by "Clear all" — everything that is not pinned."""
        return [i for i in items if not i.pinned]

    def sort_for_display(self, items: Sequence[ClipItem]) -> list[ClipItem]:
        """Most recently used first, exactly like the Win+V panel."""
        return sorted(items, key=lambda i: i.last_used_at, reverse=True)
