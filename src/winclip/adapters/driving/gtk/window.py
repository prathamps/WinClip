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
    ActivateSnippet,
    ManageHistory,
    ManageSettings,
    QueryCommands,
    QueryHistory,
)
from winclip.catalog import EMOJI, KAOMOJI, SYMBOLS  # noqa: E402

from .pages import CommandsPage, SnippetPage  # noqa: E402
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
    font-size: 0.8em;
    color: @theme_selected_bg_color;
    padding: 1px 6px;
    min-width: 0;
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
/* Selection must not recolor card text: the card keeps its own
   background, so the theme's selected-row foreground (white on light
   themes) would be unreadable. */
row.clip-card-row:selected label {
    color: @theme_fg_color;
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
/* Tab switcher in the header, kept compact. */
.panel stackswitcher button {
    padding: 0px 5px;
    min-height: 20px;
    min-width: 0;
    font-size: 0.85em;
}
.category-title {
    font-weight: 600;
    font-size: 0.8em;
    opacity: 0.6;
    margin-top: 8px;
    margin-bottom: 2px;
}
.emoji-btn {
    font-size: 1.35em;
    padding: 2px 4px;
}
.kaomoji-btn {
    font-size: 0.85em;
    padding: 4px 6px;
}
.symbol-btn {
    font-size: 1.1em;
    padding: 2px 8px;
}
.command-text {
    font-family: monospace;
    font-size: 0.85em;
}
.tool-chip {
    border-radius: 99px;
    padding: 1px 10px;
    font-size: 0.8em;
    background-color: alpha(@theme_fg_color, 0.07);
}
.tool-chip-active {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
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
        activate_snippet: ActivateSnippet,
        query_commands: QueryCommands,
    ) -> None:
        super().__init__(application=application, title="WinClip")
        self._query = query
        self._manage = manage
        self._activate = activate
        self._settings = settings
        self._activate_snippet = activate_snippet
        self._query_commands = query_commands

        # Fixed size, like the Win+V flyout: movable but never resizable.
        # This serves three purposes: the undecorated window's invisible
        # edges stop acting as resize handles (easy to grab accidentally
        # while moving the panel), tiling compositors (COSMIC auto-tile,
        # sway) float non-resizable windows instead of stretching them
        # into a tile, and the flyout keeps its Windows proportions.
        # (Gdk.Geometry min==max hints would be the classic way, but they
        # produce wrong sizes with GTK3 CSD on Wayland — set_resizable is
        # the reliable mechanism.)
        self.set_default_size(360, 480)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_skip_taskbar_hint(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.get_style_context().add_class("winclip-panel")
        self._shown_at: int = 0
        self._dialog_open = False

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

        # Header: tab switcher | Clear all | gear — like the Win+V flyout.
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.set_margin_top(8)
        header.set_margin_bottom(6)
        header.set_margin_start(8)
        header.set_margin_end(8)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(120)

        switcher = Gtk.StackSwitcher(stack=self._stack)
        switcher.set_halign(Gtk.Align.START)
        header.pack_start(switcher, True, True, 0)

        prefs_btn = Gtk.Button.new_from_icon_name(
            "emblem-system-symbolic", Gtk.IconSize.MENU
        )
        prefs_btn.set_relief(Gtk.ReliefStyle.NONE)
        prefs_btn.get_style_context().add_class("icon-button")
        prefs_btn.set_tooltip_text("Preferences")
        prefs_btn.connect("clicked", self._on_preferences)
        header.pack_end(prefs_btn, False, False, 0)

        self._clear_btn = Gtk.Button(label="Clear all")
        self._clear_btn.set_relief(Gtk.ReliefStyle.NONE)
        self._clear_btn.get_style_context().add_class("clear-all")
        self._clear_btn.set_tooltip_text("Remove everything except pinned items")
        self._clear_btn.connect("clicked", self._on_clear_all)
        header.pack_end(self._clear_btn, False, False, 0)

        panel.pack_start(header, False, False, 0)

        self._search = Gtk.SearchEntry(placeholder_text="Search")
        self._search.get_style_context().add_class("search-entry")
        self._search.connect("search-changed", lambda _e: self._apply_search())
        panel.pack_start(self._search, False, False, 0)

        # Page 1: clipboard history.
        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.get_style_context().add_class("clip-list")
        self._list.connect("row-activated", self._on_row_activated)
        self._list.set_placeholder(self._build_empty_state())

        clips_scroller = Gtk.ScrolledWindow()
        clips_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        clips_scroller.set_vexpand(True)
        clips_scroller.add(self._list)

        # Pages 2-4: snippet catalogs. Page 5: shell commands.
        self._emoji_page = SnippetPage(
            EMOJI, self._on_snippet, "emoji-btn", max_per_line=8
        )
        self._kaomoji_page = SnippetPage(
            KAOMOJI, self._on_snippet, "kaomoji-btn", max_per_line=2
        )
        self._symbols_page = SnippetPage(
            SYMBOLS, self._on_snippet, "symbol-btn", max_per_line=7
        )
        self._commands_page = CommandsPage(self._query_commands, self._on_snippet)

        for name, title, page in (
            ("clips", "📋", clips_scroller),
            ("emoji", "😊", self._emoji_page),
            ("kaomoji", "(ツ)", self._kaomoji_page),
            ("symbols", "Ω", self._symbols_page),
            ("commands", "❯_", self._commands_page),
        ):
            self._stack.add_titled(page, name, title)

        self._stack.set_margin_bottom(8)
        self._stack.connect("notify::visible-child", self._on_page_changed)
        panel.pack_start(self._stack, True, True, 0)

        self.add(panel)
        panel.show_all()
        # Pages that call show_all() during construction would otherwise
        # win the "first visible child" race; be explicit.
        self._stack.set_visible_child_name("clips")
        self._apply_search()

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
        # With no titlebar, let the user drag the panel by any spot that
        # isn't an interactive widget (header, edges, gaps): clicks on
        # buttons/entries/rows are consumed before they reach the window.
        self.connect("button-press-event", self._on_drag_press)

    def _on_drag_press(self, _widget, event) -> bool:
        if event.button == 1:
            # Restart the focus-out grace period: some compositors emit a
            # focus-out for the move grab, which must not dismiss the panel.
            self._shown_at = GLib.get_monotonic_time()
            self.begin_move_drag(
                event.button, int(event.x_root), int(event.y_root), event.time
            )
            return True
        return False

    # -- behaviour -----------------------------------------------------

    def toggle(self) -> None:
        if self.is_visible():
            self.hide()
        else:
            self.present_panel()

    def present_panel(self) -> None:
        self._search.set_text("")
        self.refresh()
        commands_tab = self._stack.get_child_by_name("commands")
        commands_tab.set_visible(self._settings.get_settings().show_commands)
        self._commands_page.refresh()
        # Always open on the clipboard tab, like Win+V.
        self._stack.set_visible_child_name("clips")
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

    def _apply_search(self) -> None:
        """Route the shared search box to whichever page is active."""
        query = self._search.get_text().strip()
        page = self._stack.get_visible_child_name()
        if page == "clips":
            self.refresh()
        elif page == "emoji":
            self._emoji_page.set_filter(query)
        elif page == "kaomoji":
            self._kaomoji_page.set_filter(query)
        elif page == "symbols":
            self._symbols_page.set_filter(query)
        elif page == "commands":
            self._commands_page.set_filter(query)

    def _on_page_changed(self, _stack, _param) -> None:
        # Clear-all only makes sense for the clipboard page.
        self._clear_btn.set_visible(
            self._stack.get_visible_child_name() == "clips"
        )
        self._apply_search()

    # -- callbacks -----------------------------------------------------

    def _on_snippet(self, text: str) -> None:
        """An emoji, symbol, kaomoji, or command was chosen."""
        self.hide()
        GLib.timeout_add(60, self._do_activate_snippet, text)

    def _do_activate_snippet(self, text: str) -> bool:
        try:
            result = self._activate_snippet.activate_text(text)
        except Exception:  # noqa: BLE001 — UI callback must not crash the loop
            log.exception("failed to activate snippet")
            return False
        if not result.pasted and self._settings.get_settings().auto_paste:
            self._notify_copy_only()
        return False  # one-shot timeout

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
        # The modal dialog takes focus; suspend hide-on-focus-out so the
        # panel (the dialog's parent) doesn't vanish underneath it.
        self._dialog_open = True
        try:
            dialog = PreferencesDialog(self, self._settings)
            dialog.run_and_apply()
        finally:
            self._dialog_open = False
        self._shown_at = GLib.get_monotonic_time()
        self.present_panel()

    def _on_key_press(self, _widget, event) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        shift = event.state & Gdk.ModifierType.SHIFT_MASK
        if keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab) and ctrl:
            self._cycle_page(backwards=bool(shift))
            return True
        # Ctrl+PgDn/PgUp: the GTK-conventional tab switch.
        if keyval == Gdk.KEY_Page_Down and ctrl:
            self._cycle_page()
            return True
        if keyval == Gdk.KEY_Page_Up and ctrl:
            self._cycle_page(backwards=True)
            return True
        # Alt+1..5 jumps straight to a tab.
        if event.state & Gdk.ModifierType.MOD1_MASK and Gdk.KEY_1 <= keyval <= Gdk.KEY_5:
            self._jump_to_page(keyval - Gdk.KEY_1)
            return True

        page = self._stack.get_visible_child_name()
        if keyval == Gdk.KEY_Down and self._search.has_focus():
            if page == "clips":
                self._list.grab_focus()
                return True
            if page == "commands":
                return self._commands_page.focus_list()
            return self._snippet_page(page).focus_first_visible()
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if page == "clips":
                row = self._list.get_selected_row()
                if isinstance(row, ClipRow):
                    self._on_row_activated(self._list, row)
                return True
            if page == "commands":
                return self._commands_page.activate_selected()
            # Snippet grids: Enter in the search box inserts the first
            # match, like the Windows emoji panel. A focused button
            # handles its own Enter.
            if self._search.has_focus():
                return self._snippet_page(page).activate_first_visible()
            return False

        if page != "clips":
            return False
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
        return False

    def _snippet_page(self, name: str):
        return {
            "emoji": self._emoji_page,
            "kaomoji": self._kaomoji_page,
            "symbols": self._symbols_page,
        }[name]

    def _visible_page_names(self) -> list[str]:
        return [
            self._stack.child_get_property(child, "name")
            for child in self._stack.get_children()
            if child.get_visible()
        ]

    def _cycle_page(self, backwards: bool = False) -> None:
        names = self._visible_page_names()
        current = self._stack.get_visible_child_name()
        if current in names:
            step = -1 if backwards else 1
            self._stack.set_visible_child_name(
                names[(names.index(current) + step) % len(names)]
            )

    def _jump_to_page(self, index: int) -> None:
        names = self._visible_page_names()
        if index < len(names):
            self._stack.set_visible_child_name(names[index])

    def _on_focus_out(self, _widget, _event) -> bool:
        # Behave like the Win+V flyout: clicking elsewhere dismisses it.
        # A short grace period absorbs the spurious focus-out some
        # compositors emit while the panel is still being mapped and
        # focused — without it the panel can hide before it is ever seen.
        if self._dialog_open:
            return False
        if GLib.get_monotonic_time() - self._shown_at < 500_000:  # 0.5 s
            return False
        self.hide()
        return False

    def _on_delete_event(self, _widget, _event) -> bool:
        self.hide()
        return True  # keep the daemon alive
