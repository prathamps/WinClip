"""Card widget for a single clipboard item, Windows 11 flyout style.

Each entry is a rounded card; the pin and delete buttons sit in the
top-right corner and appear on hover/selection (always visible for
pinned items, like Windows).
"""

from __future__ import annotations

from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from winclip.domain import ClipItem, ContentKind  # noqa: E402

from .humanize import relative_time  # noqa: E402

_THUMB_MAX_W = 220
_THUMB_MAX_H = 110
_TEXT_PREVIEW_CHARS = 240


def _icon(*names: str) -> str:
    """First icon name the current theme actually provides."""
    theme = Gtk.IconTheme.get_default()
    for name in names:
        if theme.has_icon(name):
            return name
    return names[-1]


class ClipRow(Gtk.ListBoxRow):
    """One history entry rendered as a Windows-style card."""

    def __init__(self, item: ClipItem, on_pin, on_delete) -> None:
        super().__init__()
        self.item = item
        self._on_pin = on_pin
        self._on_delete = on_delete
        self.get_style_context().add_class("clip-card-row")

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.get_style_context().add_class("clip-card")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_hexpand(True)
        content.pack_start(self._build_preview(), True, True, 0)
        content.pack_start(self._build_meta_label(), False, False, 0)
        card.pack_start(content, True, True, 0)
        card.pack_end(self._build_actions(), False, False, 0)

        self.add(card)
        self.show_all()

    def _build_preview(self) -> Gtk.Widget:
        if self.item.kind is ContentKind.IMAGE and self.item.image:
            pixbuf = self._thumbnail(self.item.image)
            if pixbuf is not None:
                image = Gtk.Image.new_from_pixbuf(pixbuf)
                image.set_halign(Gtk.Align.START)
                return image
        label = Gtk.Label(label=self.item.preview(_TEXT_PREVIEW_CHARS))
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        label.set_line_wrap(True)
        # WORD_CHAR allows breaking inside words: a wrapped label's
        # minimum width is otherwise its longest unbreakable token, so a
        # copied URL or base64 blob would stretch the whole
        # non-resizable panel.
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_lines(3)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_xalign(0.0)
        label.set_width_chars(10)
        label.set_max_width_chars(34)
        label.get_style_context().add_class("clip-text")
        return label

    def _build_meta_label(self) -> Gtk.Label:
        now = datetime.now(timezone.utc)
        parts = [relative_time(self.item.last_used_at, now)]
        if self.item.kind is ContentKind.IMAGE:
            parts.append("image")
        label = Gtk.Label(label="  ·  ".join(parts))
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class("clip-meta")
        return label

    def _build_actions(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box.set_valign(Gtk.Align.START)
        box.get_style_context().add_class("card-actions")
        if self.item.pinned:
            # Pinned cards always show their pin, like Windows.
            box.get_style_context().add_class("pinned-visible")

        pin_name = (
            _icon("view-pin-symbolic", "starred-symbolic")
            if self.item.pinned
            else _icon("view-pin-symbolic", "non-starred-symbolic")
        )
        pin_btn = Gtk.Button.new_from_icon_name(pin_name, Gtk.IconSize.MENU)
        pin_btn.set_relief(Gtk.ReliefStyle.NONE)
        pin_btn.get_style_context().add_class("icon-button")
        pin_btn.set_tooltip_text("Unpin" if self.item.pinned else "Pin")
        if self.item.pinned:
            pin_btn.get_style_context().add_class("suggested-action")
        pin_btn.connect("clicked", lambda _b: self._on_pin(self.item.id))

        del_btn = Gtk.Button.new_from_icon_name(
            _icon("window-close-symbolic", "edit-delete-symbolic"),
            Gtk.IconSize.MENU,
        )
        del_btn.set_relief(Gtk.ReliefStyle.NONE)
        del_btn.get_style_context().add_class("icon-button")
        del_btn.set_tooltip_text("Delete")
        del_btn.connect("clicked", lambda _b: self._on_delete(self.item.id))

        box.pack_start(pin_btn, False, False, 0)
        box.pack_start(del_btn, False, False, 0)
        return box

    @staticmethod
    def _thumbnail(png_data: bytes) -> GdkPixbuf.Pixbuf | None:
        try:
            loader = GdkPixbuf.PixbufLoader.new_with_type("png")
            loader.write(png_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
        except GLib.Error:
            return None
        if pixbuf is None:
            return None
        scale = min(
            _THUMB_MAX_W / pixbuf.get_width(),
            _THUMB_MAX_H / pixbuf.get_height(),
            1.0,
        )
        if scale < 1.0:
            pixbuf = pixbuf.scale_simple(
                int(pixbuf.get_width() * scale),
                int(pixbuf.get_height() * scale),
                GdkPixbuf.InterpType.BILINEAR,
            )
        return pixbuf
