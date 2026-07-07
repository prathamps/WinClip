"""The GTK application shell: single-instance daemon + panel.

Gtk.Application gives us single-instance semantics over D-Bus for
free: the first ``winclip`` process becomes the daemon; any later
``winclip toggle`` simply activates the ``toggle`` action on the
running instance and exits.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from winclip.bootstrap import Container  # noqa: E402

from .window import HistoryWindow  # noqa: E402

log = logging.getLogger(__name__)

APP_ID = "io.github.prathamps.WinClip"


class WinClipApplication(Gtk.Application):
    def __init__(self, container: Container, show_on_start: bool = False) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._container = container
        self._show_on_start = show_on_start
        self._window: HistoryWindow | None = None

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)

        for name, callback in (
            ("toggle", self._on_toggle),
            ("show", self._on_show),
            ("quit", self._on_quit),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        self._container.monitor.start()
        # Stay alive with no visible window — we are a daemon.
        self.hold()
        log.info("winclip daemon started (%s)", APP_ID)

    def do_activate(self) -> None:
        self._ensure_window()
        if self._show_on_start:
            self._show_on_start = False
            assert self._window is not None
            self._window.present_panel()

    def do_shutdown(self) -> None:
        self._container.shutdown()
        Gtk.Application.do_shutdown(self)

    def _ensure_window(self) -> HistoryWindow:
        if self._window is None:
            self._window = HistoryWindow(
                application=self,
                query=self._container.query,
                manage=self._container.manage,
                activate=self._container.activate,
                settings=self._container.settings,
            )
        return self._window

    def _on_toggle(self, _action, _param) -> None:
        self._ensure_window().toggle()

    def _on_show(self, _action, _param) -> None:
        self._ensure_window().present_panel()

    def _on_quit(self, _action, _param) -> None:
        self.release()
        self.quit()


def send_action_to_running_instance(action: str) -> bool:
    """Poke the daemon over D-Bus. Returns False when it is not running."""
    probe = Gio.Application(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
    try:
        probe.register(None)
    except GLib.Error as exc:
        log.error("could not reach the session bus: %s", exc.message)
        return False
    if not probe.get_is_remote():
        # We accidentally became the primary instance — bail out so the
        # caller can start a real daemon instead.
        return False
    probe.activate_action(action, None)
    return True
