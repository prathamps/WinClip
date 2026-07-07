"""Panel pages beyond the clipboard list: snippet grids and commands.

``SnippetPage`` renders a static catalog (emoji, kaomoji, symbols) as
categorised button grids with search filtering. ``CommandsPage``
browses shell history grouped by tool. Both hand the chosen text to a
callback — the window decides what activation means.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from winclip.application import QueryCommands  # noqa: E402
from winclip.catalog import Catalog  # noqa: E402


class SnippetPage(Gtk.ScrolledWindow):
    """A searchable, categorised grid of one-click text snippets."""

    def __init__(
        self,
        catalog: Catalog,
        on_activate: Callable[[str], None],
        button_css: str,
    ) -> None:
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_vexpand(True)

        self._sections: list[tuple[Gtk.Label, Gtk.FlowBox, list]] = []
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        column.set_margin_start(10)
        column.set_margin_end(10)
        column.set_margin_bottom(10)

        for category, entries in catalog.items():
            title = Gtk.Label(label=category, halign=Gtk.Align.START)
            title.get_style_context().add_class("category-title")
            column.pack_start(title, False, False, 0)

            grid = Gtk.FlowBox()
            grid.set_selection_mode(Gtk.SelectionMode.NONE)
            grid.set_max_children_per_line(30)
            grid.set_homogeneous(False)
            widgets = []
            for text, name in entries:
                button = Gtk.Button(label=text)
                button.set_relief(Gtk.ReliefStyle.NONE)
                button.set_tooltip_text(name)
                button.get_style_context().add_class(button_css)
                button.connect(
                    "clicked", lambda _b, t=text: on_activate(t)
                )
                grid.add(button)
                widgets.append((button, text, f"{text} {name}".lower()))
            column.pack_start(grid, False, False, 0)
            self._sections.append((title, grid, widgets))

        self.add(column)
        column.show_all()

    def set_filter(self, query: str) -> None:
        needle = query.strip().lower()
        for title, grid, widgets in self._sections:
            visible = 0
            for button, _text, haystack in widgets:
                match = not needle or needle in haystack
                # FlowBox wraps each button in a FlowBoxChild.
                button.get_parent().set_visible(match)
                visible += match
            title.set_visible(visible > 0)
            grid.set_visible(visible > 0)


class CommandsPage(Gtk.Box):
    """Shell history browser: pick a tool, click a command to paste it."""

    def __init__(
        self,
        query_commands: QueryCommands,
        on_activate: Callable[[str], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._query_commands = query_commands
        self._on_activate = on_activate
        self._search = ""

        self._tool_picker = Gtk.ComboBoxText()
        self._tool_picker.set_margin_start(10)
        self._tool_picker.set_margin_end(10)
        self._picker_handler = self._tool_picker.connect(
            "changed", lambda _c: self._rebuild_list()
        )
        self.pack_start(self._tool_picker, False, False, 0)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.get_style_context().add_class("clip-list")
        self._list.connect("row-activated", self._on_row_activated)
        self._list.set_placeholder(self._build_empty_state())

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.add(self._list)
        self.pack_start(scroller, True, True, 0)

    @staticmethod
    def _build_empty_state() -> Gtk.Widget:
        label = Gtk.Label(
            label="No shell commands found.\n"
            "History is read from bash, zsh, and fish.\n"
            "(Enable/disable this tab in Preferences.)"
        )
        label.set_justify(Gtk.Justification.CENTER)
        label.get_style_context().add_class("empty-subtitle")
        label.set_margin_top(48)
        label.show()
        return label

    def refresh(self) -> None:
        """Re-read history and rebuild the tool picker + command list."""
        selected = self._selected_tool()
        with self._tool_picker.handler_block(self._picker_handler):
            self._tool_picker.remove_all()
            self._tool_picker.append("", "All tools")
            for usage in self._query_commands.tools()[:30]:
                self._tool_picker.append(
                    usage.tool, f"{usage.tool} ({usage.count})"
                )
            if not self._tool_picker.set_active_id(selected or ""):
                self._tool_picker.set_active_id("")
        self._rebuild_list()

    def set_filter(self, query: str) -> None:
        self._search = query.strip()
        self._rebuild_list()

    def _selected_tool(self) -> str | None:
        active = self._tool_picker.get_active_id()
        return active or None

    def _rebuild_list(self) -> None:
        for child in self._list.get_children():
            self._list.remove(child)
        entries = self._query_commands.commands(
            self._selected_tool(), self._search
        )[:200]
        for entry in entries:
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("clip-card-row")
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            card.get_style_context().add_class("clip-card")
            label = Gtk.Label(label=entry.command)
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_xalign(0.0)
            label.get_style_context().add_class("command-text")
            card.pack_start(label, True, True, 0)
            row.add(card)
            row.command = entry.command
            self._list.add(row)
        self._list.show_all()
        first = self._list.get_row_at_index(0)
        if first is not None:
            self._list.select_row(first)

    def _on_row_activated(self, _list, row) -> None:
        command = getattr(row, "command", None)
        if command:
            # Defer so the click's button-release doesn't leak into the
            # window that receives the paste.
            GLib.idle_add(self._on_activate, command)

    def activate_selected(self) -> bool:
        row = self._list.get_selected_row()
        if row is not None:
            self._on_row_activated(self._list, row)
            return True
        return False
