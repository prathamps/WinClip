"""Wayland layer-shell placement for the panel.

Tiling compositors (Hyprland, sway, river, niri) tile every ordinary
toplevel, which would make the Win+V panel reshuffle the layout each
time it opens. A layer-shell surface sits above the window stack
instead, so the panel opens the same way whether the focused window
is tiled or floating. GNOME does not offer layer-shell to applications,
so the panel stays a normal toplevel there.

Requires the ``GtkLayerShell`` introspection data (``gtk-layer-shell``
on Arch, ``gir1.2-gtklayershell-0.1`` on Debian); without it the
caller falls back to the plain toplevel.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

log = logging.getLogger(__name__)

_NAMESPACE = "winclip"


def attach_layer_shell(window: Gtk.Window) -> bool:
    """Turn ``window`` into an overlay layer surface. Must run before the
    window is realized. Returns False when layer-shell is unavailable."""
    shell = _load_layer_shell()
    if shell is None or not shell.is_supported():
        log.debug("layer-shell unavailable; the panel is a regular toplevel")
        return False
    shell.init_for_window(window)
    shell.set_namespace(window, _NAMESPACE)
    shell.set_layer(window, shell.Layer.OVERLAY)
    shell.set_keyboard_mode(window, shell.KeyboardMode.ON_DEMAND)
    log.info("panel placed as a layer-shell surface")
    return True


def _load_layer_shell():
    try:
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell
    except (ValueError, ImportError):
        return None
    return GtkLayerShell
