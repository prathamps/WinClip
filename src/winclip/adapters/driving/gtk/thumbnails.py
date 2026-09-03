"""Thumbnail support for image clips.

:class:`ThumbnailCache` is a small pure LRU keyed by content hash, so
the same screenshot is decoded once per daemon lifetime no matter how
often the panel opens. :func:`decode_thumbnail` asks GdkPixbuf to
decode straight at thumbnail size, which is far cheaper than decoding
a full-resolution PNG and scaling it afterwards.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar

T = TypeVar("T")

DEFAULT_CAPACITY = 128


class ThumbnailCache(Generic[T]):
    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._entries: OrderedDict[str, T] = OrderedDict()

    def get(self, key: str) -> T | None:
        if key not in self._entries:
            return None
        self._entries.move_to_end(key)
        return self._entries[key]

    def put(self, key: str, value: T) -> None:
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)

    def __contains__(self, key: str) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)


def fit_within(width: int, height: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Dimensions scaled down (never up) to fit the given box."""
    scale = min(max_w / width, max_h / height, 1.0)
    return max(1, int(width * scale)), max(1, int(height * scale))


def decode_thumbnail(png_data: bytes, max_w: int, max_h: int):
    """A pixbuf no larger than ``max_w`` × ``max_h``, or None if the
    bytes are not a decodable image."""
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib

    def shrink_on_size_prepared(loader, width, height):
        loader.set_size(*fit_within(width, height, max_w, max_h))

    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    loader.connect("size-prepared", shrink_on_size_prepared)
    try:
        loader.write(png_data)
        loader.close()
    except GLib.Error:
        return None
    return loader.get_pixbuf()
