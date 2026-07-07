"""Wayland clipboard monitor.

Wayland only exposes clipboard contents to the focused surface, so a
background daemon cannot use the regular clipboard API. ``wl-paste
--watch`` uses the data-control protocol (wlr-data-control /
ext-data-control), which exists precisely for clipboard managers and
is supported by GNOME (Mutter 46+), KDE, and all wlroots compositors.

We run ``wl-paste --watch`` purely as a change notifier and then fetch
the actual content with one-shot ``wl-paste`` calls, choosing image
over text when both are offered (matching Windows behaviour for
screenshots and image copies).
"""

from __future__ import annotations

import logging
import subprocess
import threading

from winclip.application.ports.driving import CapturesClipboard

log = logging.getLogger(__name__)

_TEXT_TYPES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "STRING")


class WaylandClipboardMonitor:
    def __init__(self, capture: CapturesClipboard) -> None:
        self._capture = capture
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def start(self) -> None:
        try:
            # `wl-paste --watch <cmd>` runs <cmd> on every clipboard
            # change; we use `echo` as a cheap change signal and read
            # its output line by line.
            self._proc = subprocess.Popen(
                ["wl-paste", "--watch", "echo", "changed"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log.error(
                "wl-paste not found — install the wl-clipboard package to "
                "enable clipboard capture on Wayland"
            )
            return
        self._thread = threading.Thread(
            target=self._watch_loop, name="winclip-wl-monitor", daemon=True
        )
        self._thread.start()
        log.info("wayland clipboard monitor started")

    def stop(self) -> None:
        self._stopping.set()
        if self._proc is not None:
            self._proc.terminate()

    def _watch_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for _ in self._proc.stdout:
            if self._stopping.is_set():
                break
            try:
                self._capture_current()
            except Exception:  # noqa: BLE001 — the monitor must survive anything
                log.exception("error while capturing clipboard change")
        if not self._stopping.is_set():
            log.warning(
                "wl-paste watcher exited unexpectedly; clipboard capture stopped. "
                "Does your compositor support the data-control protocol?"
            )

    def _capture_current(self) -> None:
        types = self._offered_types()
        if any(t.startswith("image/png") for t in types):
            data = self._read(["wl-paste", "--type", "image/png"])
            if data:
                self._capture.capture_image(data)
            return
        if any(t in types for t in _TEXT_TYPES):
            data = self._read(["wl-paste", "--no-newline", "--type", "text"])
            if data:
                self._capture.capture_text(data.decode("utf-8", errors="replace"))

    @staticmethod
    def _offered_types() -> list[str]:
        try:
            out = subprocess.run(
                ["wl-paste", "--list-types"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return out.stdout.decode("utf-8", errors="replace").split()
        except (OSError, subprocess.TimeoutExpired):
            return []

    @staticmethod
    def _read(cmd: list[str]) -> bytes:
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=10, check=False)
            return out.stdout if out.returncode == 0 else b""
        except (OSError, subprocess.TimeoutExpired):
            return b""
