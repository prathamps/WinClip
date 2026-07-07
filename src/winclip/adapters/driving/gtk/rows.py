"""List-row widget for a single clipboard item."""

from __future__ import annotations

from datetime import datetime, timezone

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402

from winclip.domain import ClipItem, ContentKind  # noqa: E402

from .humanize import relative_time  # noqa: E402

_THUMB_MAX_W = 260
_THUMB_MAX_H = 96
_TEXT_PREVIEW_CHARS = 240


class ClipRow(Gtk.ListBoxRow):
    """One history entry: preview, timestamp, pin and delete buttons."""

    def __init__(self, item: ClipItem, on_pin, on_delete) -> None:
        super().__init__()
        self.item = item
        self._on_pin = on_pin
        self._on_delete = on_delete

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.get_style_context().add_class("clip-row")
        if item.pinned:
            outer.get_style_context().add_class("pinned")

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_hexpand(True)
        content.pack_start(self._build_preview(), True, True, 0)
        content.pack_start(self._build_meta_label(), False, False, 0)
        outer.pack_start(content, True, True, 0)
        outer.pack_end(self._build_buttons(), False, False, 0)

        self.add(outer)
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
        label.set_line_wrap(True)
        label.set_lines(3)
        label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        label.set_xalign(0.0)
        label.get_style_context().add_class("clip-text")
        return label

    def _build_meta_label(self) -> Gtk.Label:
        now = datetime.now(timezone.utc)
        parts = [relative_time(self.item.last_used_at, now)]
        if self.item.kind is ContentKind.IMAGE:
            parts.append("image")
        if self.item.pinned:
            parts.append("pinned")
        label = Gtk.Label(label="  ·  ".join(parts))
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class("clip-meta")
        return label

    def _build_buttons(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_valign(Gtk.Align.CENTER)

        pin_icon = "starred-symbolic" if self.item.pinned else "non-starred-symbolic"
        pin_btn = Gtk.Button.new_from_icon_name(pin_icon, Gtk.IconSize.MENU)
        pin_btn.set_relief(Gtk.ReliefStyle.NONE)
        pin_btn.set_tooltip_text("Unpin" if self.item.pinned else "Pin")
        pin_btn.connect("clicked", lambda _b: self._on_pin(self.item.id))

        del_btn = Gtk.Button.new_from_icon_name(
            "window-close-symbolic", Gtk.IconSize.MENU
        )
        del_btn.set_relief(Gtk.ReliefStyle.NONE)
        del_btn.set_tooltip_text("Delete")
        del_btn.connect("clicked", lambda _b: self._on_delete(self.item.id))

        box.pack_start(del_btn, False, False, 0)
        box.pack_start(pin_btn, False, False, 0)
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
