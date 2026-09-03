"""Blend the panel into the active Omarchy theme.

Omarchy (https://omarchy.org) keeps the active theme's palette in
``~/.local/state/omarchy/current/theme/colors.toml`` and re-renders
every themed app on ``omarchy theme set``. GTK apps only receive a
light/dark Adwaita switch, so WinClip maps the palette onto GTK's
named colours itself, styled after Omarchy's own clipboard menu: theme
background and text, the accent on the selected item, the ``monospace``
font Omarchy configures through fontconfig, and Hyprland's corner
rounding.

This module produces CSS text only; the panel applies it. It imports
no GTK so the mapping is unit-testable headless.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_KEY_VALUE = re.compile(r'^\s*([A-Za-z_][\w-]*)\s*=\s*"([^"]*)"')
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def colors_file() -> Path:
    state = os.environ.get("XDG_STATE_HOME", "~/.local/state")
    return Path(state).expanduser() / "omarchy" / "current" / "theme" / "colors.toml"


def parse_colors(text: str) -> dict[str, str]:
    """The ``key = "value"`` pairs of a flat colors.toml.

    Python 3.10 has no tomllib, and the file is flat, so a line parser
    is enough; anything else (comments, numbers, tables) is skipped."""
    matches = (_KEY_VALUE.match(line) for line in text.splitlines())
    return {match.group(1): match.group(2) for match in matches if match}


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    foreground: str
    accent: str
    muted: str

    @classmethod
    def from_colors(cls, colors: dict[str, str]) -> Palette:
        """Raises ValueError when the palette lacks the essential colours
        or holds anything that is not a ``#rrggbb`` colour."""
        try:
            background = colors["background"]
            foreground = colors["foreground"]
        except KeyError as missing:
            raise ValueError(f"colors.toml lacks {missing}") from None
        dark = colors.get("mode", _mode_of(background)) == "dark"
        surface_key = "lighter_background" if dark else "dark_background"
        palette = cls(
            background=background,
            surface=colors.get(surface_key, background),
            foreground=foreground,
            accent=colors.get("accent", foreground),
            muted=colors.get("muted", foreground),
        )
        for name, value in vars(palette).items():
            if not _HEX_COLOR.match(value):
                raise ValueError(f"{name} is not a #rrggbb colour: {value!r}")
        return palette


def _mode_of(hex_color: str) -> str:
    if not _HEX_COLOR.match(hex_color):
        return "dark"
    red, green, blue = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "light" if luminance > 128 else "dark"


def palette_css(palette: Palette, rounding: int | None) -> str:
    named_colors = {
        "theme_bg_color": palette.background,
        "theme_base_color": palette.surface,
        "theme_fg_color": palette.foreground,
        "theme_text_color": palette.foreground,
        "theme_selected_bg_color": palette.accent,
        "theme_selected_fg_color": palette.background,
        "borders": f"alpha({palette.foreground}, 0.4)",
        "insensitive_bg_color": palette.background,
        "insensitive_fg_color": palette.muted,
        "theme_unfocused_bg_color": palette.background,
        "theme_unfocused_base_color": palette.surface,
        "theme_unfocused_fg_color": palette.foreground,
        "theme_unfocused_text_color": palette.foreground,
        "theme_unfocused_selected_bg_color": palette.accent,
        "theme_unfocused_selected_fg_color": palette.background,
        "unfocused_borders": f"alpha({palette.foreground}, 0.4)",
        "unfocused_insensitive_color": palette.muted,
    }
    lines = [f"@define-color {name} {value};" for name, value in named_colors.items()]
    lines += [
        "window.winclip-panel { font-family: monospace; }",
        ".panel { border: 2px solid @theme_fg_color; }",
        "row.clip-card-row:hover .clip-card, row.clip-card-row:selected .clip-card {"
        " background-color: alpha(@theme_fg_color, 0.08);"
        " border-color: alpha(@theme_fg_color, 0.25); }",
        "row.clip-card-row:selected label.clip-text { color: @theme_selected_bg_color; }",
    ]
    if rounding is not None:
        lines.append(
            "window.winclip-panel decoration, .panel, .clip-card, .search-entry {"
            f" border-radius: {rounding}px; }}"
        )
    return "\n".join(lines) + "\n"


def hyprland_rounding() -> int | None:
    if "HYPRLAND_INSTANCE_SIGNATURE" not in os.environ or not shutil.which("hyprctl"):
        return None
    try:
        out = subprocess.run(
            ["hyprctl", "getoption", "decoration:rounding", "-j"],
            capture_output=True,
            timeout=2,
            check=True,
        )
        return int(json.loads(out.stdout)["int"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


def omarchy_theme_css() -> str:
    """CSS that blends the panel into the active Omarchy theme; empty
    when Omarchy is not managing this desktop."""
    path = colors_file()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        palette = Palette.from_colors(parse_colors(text))
    except ValueError as exc:
        log.warning("ignoring Omarchy palette at %s: %s", path, exc)
        return ""
    return palette_css(palette, hyprland_rounding())
