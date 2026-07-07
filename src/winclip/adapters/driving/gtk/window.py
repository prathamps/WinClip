"""The clipboard history panel — WinClip's answer to the Win+V window.

Styled after the Windows 11 clipboard flyout: an undecorated rounded
panel with a small "Clipboard" header, a Clear-all button, and a
scrolling stack of content cards whose actions appear on hover.

The window talks to the application core exclusively through the
driving ports (QueryHistory, ManageHistory, ActivateClip,
ManageSettings); it knows nothing about SQLite or Wayland.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
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
/* Let the rounded panel show through the window corners. */
window.winclip-panel {
    background: transparent;
}
window.winclip-panel decoration {
    border-radius: 12px;
}
/* The empty CSD titlebar must take no space. */
window.winclip-panel headerbar,
window.winclip-panel box.titlebar {
    min-height: 0;
    padding: 0;
    margin: 0;
    border: none;
    background: transparent;
    box-shadow: none;
}
.panel {
    background-color: @theme_bg_color;
    border-radius: 12px;
    border: 1px solid alpha(@borders, 0.7);
}
.panel-title {
    font-weight: 600;
    font-size: 1.0em;
}
.clear-all {
    font-size: 0.85em;
    color: @theme_selected_bg_color;
    padding: 2px 8px;
}
.icon-button {
    padding: 2px;
    min-width: 22px;
    min-height: 22px;
}
.search-entry {
    border-radius: 6px;
    margin: 0 12px 8px 12px;
}
list.clip-list, list.clip-list row {
    background: transparent;
}
row.clip-card-row {
    padding: 0;
    margin: 4px 12px;
}
.clip-card {
    background-color: @theme_base_color;
    border: 1px solid alpha(@borders, 0.5);
    border-radius: 8px;
    padding: 10px 12px 8px 12px;
    transition: background-color 100ms ease;
}
row.clip-card-row:hover .clip-card,
row.clip-card-row:selected .clip-card {
    background-color: shade(@theme_base_color, 0.96);
    border-color: alpha(@borders, 0.9);
}
row.clip-card-row:selected {
    background: transparent;
    outline: none;
}
.clip-text {
    font-size: 0.92em;
}
.clip-meta {
    font-size: 0.75em;
    opacity: 0.55;
}
.card-actions {
    opacity: 0;
    transition: opacity 120ms ease;
}
row.clip-card-row:hover .card-actions,
row.clip-card-row:selected .card-actions,
.card-actions.pinned-visible {
    opacity: 1;
}
.empty-title {
    font-weight: 600;
    font-size: 1.05em;
}
.empty-subtitle {
    font-size: 0.9em;
    opacity: 0.55;
}
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

        self.set_default_size(360, 480)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_skip_taskbar_hint(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.get_style_context().add_class("winclip-panel")
        self._shown_at: int = 0

        # An empty client-side titlebar removes the compositor's
        # server-side decorations (set_decorated(False) alone still gets
        # a titlebar from compositors like cosmic-comp, which default
        # undecorated Wayland clients to SSD).
        empty_titlebar = Gtk.Box()
        empty_titlebar.show()
        self.set_titlebar(empty_titlebar)

        # An RGBA visual lets the corners outside the border-radius stay
        # transparent (X11 needs this; Wayland composites anyway).
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_app_paintable(True)

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
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        panel.get_style_context().add_class("panel")

        # Header: "Clipboard" | gear | Clear all — like the Win+V flyout.
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_top(12)
        header.set_margin_bottom(8)
        header.set_margin_start(14)
        header.set_margin_end(10)

        title = Gtk.Label(label="Clipboard")
        title.get_style_context().add_class("panel-title")
        title.set_halign(Gtk.Align.START)
        header.pack_start(title, True, True, 0)

        prefs_btn = Gtk.Button.new_from_icon_name(
            "emblem-system-symbolic", Gtk.IconSize.MENU
        )
        prefs_btn.set_relief(Gtk.ReliefStyle.NONE)
        prefs_btn.get_style_context().add_class("icon-button")
        prefs_btn.set_tooltip_text("Preferences")
        prefs_btn.connect("clicked", self._on_preferences)
        header.pack_end(prefs_btn, False, False, 0)

        clear_btn = Gtk.Button(label="Clear all")
        clear_btn.set_relief(Gtk.ReliefStyle.NONE)
        clear_btn.get_style_context().add_class("clear-all")
        clear_btn.set_tooltip_text("Remove everything except pinned items")
        clear_btn.connect("clicked", self._on_clear_all)
        header.pack_end(clear_btn, False, False, 0)

        panel.pack_start(header, False, False, 0)

        self._search = Gtk.SearchEntry(placeholder_text="Search clipboard history")
        self._search.get_style_context().add_class("search-entry")
        self._search.connect("search-changed", lambda _e: self.refresh())
        panel.pack_start(self._search, False, False, 0)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.get_style_context().add_class("clip-list")
        self._list.connect("row-activated", self._on_row_activated)
        self._list.set_placeholder(self._build_empty_state())

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_margin_bottom(8)
        scroller.add(self._list)
        panel.pack_start(scroller, True, True, 0)

        self.add(panel)
        panel.show_all()

    def _build_empty_state(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_top(48)
        box.set_margin_bottom(48)
        title = Gtk.Label(label="Nothing here yet")
        title.get_style_context().add_class("empty-title")
        subtitle = Gtk.Label(
            label="Copied text and images will show up here.\nPress Enter to paste."
        )
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.get_style_context().add_class("empty-subtitle")
        box.pack_start(title, False, False, 0)
        box.pack_start(subtitle, False, False, 0)
        box.show_all()
        return box

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
        self._shown_at = GLib.get_monotonic_time()
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
        # A short grace period absorbs the spurious focus-out some
        # compositors emit while the panel is still being mapped and
        # focused — without it the panel can hide before it is ever seen.
        if GLib.get_monotonic_time() - self._shown_at < 500_000:  # 0.5 s
            return False
        self.hide()
        return False

    def _on_delete_event(self, _widget, _event) -> bool:
        self.hide()
        return True  # keep the daemon alive
