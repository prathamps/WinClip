"""ClipboardWriter implementations.

* :class:`WlClipboardWriter` — Wayland, shells out to ``wl-copy``.
  ``wl-copy`` forks into the background and keeps serving the
  selection, which makes it reliable regardless of our window state.
* :class:`GtkClipboardWriter` — X11, uses the GTK clipboard with
  ``store()`` so content survives even if the daemon exits.
"""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


class ClipboardWriteError(RuntimeError):
    pass


class WlClipboardWriter:
    def write_text(self, text: str) -> None:
        self._run(["wl-copy"], text.encode("utf-8"))

    def write_image(self, png_data: bytes) -> None:
        self._run(["wl-copy", "--type", "image/png"], png_data)

    @staticmethod
    def _run(cmd: list[str], data: bytes) -> None:
        try:
            subprocess.run(cmd, input=data, check=True, timeout=5)
        except FileNotFoundError as exc:
            raise ClipboardWriteError(
                "wl-copy not found — install the wl-clipboard package"
            ) from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ClipboardWriteError(f"wl-copy failed: {exc}") from exc


class GtkClipboardWriter:
    """X11 clipboard writer. GTK is imported lazily so that headless
    environments (tests, CI) never touch it."""

    def __init__(self) -> None:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        self._gdk = Gdk
        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

    def write_text(self, text: str) -> None:
        self._clipboard.set_text(text, -1)
        self._clipboard.store()

    def write_image(self, png_data: bytes) -> None:
        from gi.repository import GdkPixbuf

        loader = GdkPixbuf.PixbufLoader.new_with_type("png")
        loader.write(png_data)
        loader.close()
        self._clipboard.set_image(loader.get_pixbuf())
        self._clipboard.store()
