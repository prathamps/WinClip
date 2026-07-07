"""The clipboard history panel — WinClip's answer to the Win+V window.

The window talks to the application core exclusively through the
driving ports (QueryHistory, ManageHistory, ActivateClip,
ManageSettings); it knows nothing about SQLite or Wayland.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from winclip.application import (  # noqa: E402
    ActivateClip,
    ManageHistory,
    ManageSettings,
    QueryHistory,
)

from .preferences import PreferencesDialog  # noqa: E402
from .rows import ClipRow  # noqa: E402

log = logging.getLogger(__name__)

_CSS = b"""
.clip-row { padding: 8px 10px; }
.clip-row.pinned { border-left: 3px solid @theme_selected_bg_color; }
.clip-text { font-size: 0.95em; }
.clip-meta { font-size: 0.78em; opacity: 0.6; }
.empty-state { font-size: 1.05em; opacity: 0.55; padding: 24px; }
"""


class HistoryWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        query: QueryHistory,
        manage: ManageHistory,
        activate: ActivateClip,
        settings: ManageSettings,
    ) -> None:
        super().__init__(application=application, title="WinClip")
        self._query = query
        self._manage = manage
        self._activate = activate
        self._settings = settings

        self.set_default_size(400, 520)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_skip_taskbar_hint(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)

        self._install_css()
        self._build_ui()
        self._connect_signals()

    # -- construction -------------------------------------------------

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self) -> None:
        header = Gtk.HeaderBar(title="Clipboard")
        header.set_show_close_button(False)

        prefs_btn = Gtk.Button.new_from_icon_name(
            "emblem-system-symbolic", Gtk.IconSize.MENU
        )
        prefs_btn.set_tooltip_text("Preferences")
        prefs_btn.connect("clicked", self._on_preferences)
        header.pack_end(prefs_btn)

        clear_btn = Gtk.Button(label="Clear all")
        clear_btn.set_tooltip_text("Remove everything except pinned items")
        clear_btn.connect("clicked", self._on_clear_all)
        header.pack_start(clear_btn)
        self.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._search = Gtk.SearchEntry(placeholder_text="Search clipboard history")
        self._search.set_margin_top(8)
        self._search.set_margin_bottom(8)
        self._search.set_margin_start(8)
        self._search.set_margin_end(8)
        self._search.connect("search-changed", lambda _e: self.refresh())
        box.pack_start(self._search, False, False, 0)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.connect("row-activated", self._on_row_activated)

        self._empty = Gtk.Label(label="Clipboard history is empty.\nCopy something!")
        self._empty.set_justify(Gtk.Justification.CENTER)
        self._empty.get_style_context().add_class("empty-state")
        self._list.set_placeholder(self._empty)
        self._empty.show()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.add(self._list)
        box.pack_start(scroller, True, True, 0)

        self.add(box)
        box.show_all()

    def _connect_signals(self) -> None:
        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("delete-event", self._on_delete_event)

    # -- behaviour -----------------------------------------------------

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.present_panel()

    def present_panel(self) -> None:
        self.refresh()
        self._search.set_text("")
        self.present()
        self._search.grab_focus()

    def refresh(self) -> None:
        for child in self._list.get_children():
            self._list.remove(child)
        query = self._search.get_text().strip()
        items = self._query.search(query) if query else self._query.list_items()
        for item in items:
            self._list.add(ClipRow(item, self._on_pin, self._on_delete))
        first = self._list.get_row_at_index(0)
        if first is not None:
            self._list.select_row(first)

    # -- callbacks -----------------------------------------------------

    def _on_row_activated(self, _list, row: ClipRow) -> None:
        clip_id = row.item.id
        self.hide()
        # Defer past the hide so the compositor can return focus to the
        # target window before we copy + inject Ctrl+V.
        GLib.timeout_add(60, self._do_activate, clip_id)

    def _do_activate(self, clip_id: str) -> bool:
        try:
            result = self._activate.activate(clip_id)
        except Exception:  # noqa: BLE001 — UI callback must not crash the loop
            log.exception("failed to activate clip %s", clip_id)
            return False
        if not result.pasted and self._settings.get_settings().auto_paste:
            self._notify_copy_only()
        return False  # one-shot timeout

    def _notify_copy_only(self) -> None:
        from gi.repository import Gio

        app = self.get_application()
        if app is None:
            return
        note = Gio.Notification.new("Copied to clipboard")
        note.set_body("Press Ctrl+V to paste (no key-injection tool found).")
        app.send_notification("winclip-paste-fallback", note)

    def _on_pin(self, clip_id: str) -> None:
        self._manage.toggle_pin(clip_id)
        self.refresh()

    def _on_delete(self, clip_id: str) -> None:
        self._manage.delete(clip_id)
        self.refresh()

    def _on_clear_all(self, _btn) -> None:
        removed = self._manage.clear()
        log.info("cleared %d items", removed)
        self.refresh()

    def _on_preferences(self, _btn) -> None:
        dialog = PreferencesDialog(self, self._settings)
        dialog.run_and_apply()
        self.refresh()

    def _on_key_press(self, _widget, event) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        if keyval == Gdk.KEY_Delete and not self._search.has_focus():
            row = self._list.get_selected_row()
            if isinstance(row, ClipRow):
                self._on_delete(row.item.id)
            return True
        if (
            keyval in (Gdk.KEY_p, Gdk.KEY_P)
            and event.state & Gdk.ModifierType.CONTROL_MASK
        ):
            row = self._list.get_selected_row()
            if isinstance(row, ClipRow):
                self._on_pin(row.item.id)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            row = self._list.get_selected_row()
            if isinstance(row, ClipRow):
                self._on_row_activated(self._list, row)
            return True
        return False

    def _on_focus_out(self, _widget, _event) -> bool:
        # Behave like the Win+V flyout: clicking elsewhere dismisses it.
        self.hide()
        return False

    def _on_delete_event(self, _widget, _event) -> bool:
        self.hide()
        return True  # keep the daemon alive
