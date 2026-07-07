"""X11 clipboard monitor.

On X11 the GTK clipboard emits ``owner-change`` whenever any
application takes ownership of the CLIPBOARD selection, which lets a
background daemon observe every copy without polling. Runs entirely on
the GTK main loop.
"""

from __future__ import annotations

import logging

from winclip.application.ports.driving import CapturesClipboard

log = logging.getLogger(__name__)


class X11ClipboardMonitor:
    def __init__(self, capture: CapturesClipboard) -> None:
        self._capture = capture
        self._handler_id: int | None = None
        self._clipboard = None

    def start(self) -> None:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self._handler_id = self._clipboard.connect(
            "owner-change", self._on_owner_change
        )
        log.info("x11 clipboard monitor started")

    def stop(self) -> None:
        if self._clipboard is not None and self._handler_id is not None:
            self._clipboard.disconnect(self._handler_id)
            self._handler_id = None

    def _on_owner_change(self, clipboard, _event) -> None:
        try:
            if clipboard.wait_is_image_available():
                pixbuf = clipboard.wait_for_image()
                if pixbuf is not None:
                    ok, png = pixbuf.save_to_bufferv("png", [], [])
                    if ok:
                        self._capture.capture_image(bytes(png))
                return
            text = clipboard.wait_for_text()
            if text:
                self._capture.capture_text(text)
        except Exception:  # noqa: BLE001 — the monitor must survive anything
            log.exception("error while capturing clipboard change")
