"""Small preferences dialog bound to the ManageSettings port."""

from __future__ import annotations

import dataclasses

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from winclip.application import ManageSettings  # noqa: E402


class PreferencesDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, settings: ManageSettings) -> None:
        super().__init__(
            title="WinClip Preferences",
            transient_for=parent,
            modal=True,
        )
        self._settings = settings
        current = settings.get_settings()

        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(row_spacing=10, column_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        self._max_items = Gtk.SpinButton.new_with_range(1, 1000, 1)
        self._max_items.set_value(current.max_items)
        self._attach(grid, 0, "History size (unpinned items)", self._max_items)

        self._capture_images = Gtk.Switch(halign=Gtk.Align.START)
        self._capture_images.set_active(current.capture_images)
        self._attach(grid, 1, "Capture images", self._capture_images)

        self._auto_paste = Gtk.Switch(halign=Gtk.Align.START)
        self._auto_paste.set_active(current.auto_paste)
        self._attach(grid, 2, "Paste automatically on select", self._auto_paste)

        self.get_content_area().add(grid)
        grid.show_all()

    @staticmethod
    def _attach(grid: Gtk.Grid, row: int, text: str, widget: Gtk.Widget) -> None:
        label = Gtk.Label(label=text, halign=Gtk.Align.START, hexpand=True)
        grid.attach(label, 0, row, 1, 1)
        grid.attach(widget, 1, row, 1, 1)

    def run_and_apply(self) -> None:
        if self.run() == Gtk.ResponseType.OK:
            current = self._settings.get_settings()
            updated = dataclasses.replace(
                current,
                max_items=int(self._max_items.get_value()),
                capture_images=self._capture_images.get_active(),
                auto_paste=self._auto_paste.get_active(),
            )
            self._settings.update_settings(updated)
        self.destroy()
