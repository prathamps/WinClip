import pytest

from winclip.adapters.driving.gtk.omarchy_theme import (
    Palette,
    omarchy_theme_css,
    palette_css,
    parse_colors,
)

DARK_THEME = """\
mode = "dark"

accent = "#7daea3"
muted = "#665c54"
# a comment
background = "#282828"
lighter_background = "#3c3836"
dark_background = "#1e1e1e"
foreground = "#d4be98"
background-alpha = 1.0
"""

LIGHT_THEME = """\
mode = "light"
accent = "#1e66f5"
muted = "#acb0be"
background = "#eff1f5"
dark_background = "#e3e4e8"
lighter_background = "#dce0e8"
foreground = "#4c4f69"
"""


class TestParsingColorsToml:
    def test_reads_quoted_string_pairs(self):
        colors = parse_colors(DARK_THEME)
        assert colors["background"] == "#282828"
        assert colors["mode"] == "dark"

    def test_skips_comments_and_unquoted_values(self):
        colors = parse_colors(DARK_THEME)
        assert "background-alpha" not in colors
        assert "#" not in colors

    def test_empty_file_yields_no_colors(self):
        assert parse_colors("") == {}


class TestBuildingThePalette:
    def test_dark_theme_uses_the_lighter_background_for_cards(self):
        palette = Palette.from_colors(parse_colors(DARK_THEME))
        assert palette.surface == "#3c3836"
        assert palette.accent == "#7daea3"

    def test_light_theme_uses_the_darker_background_for_cards(self):
        palette = Palette.from_colors(parse_colors(LIGHT_THEME))
        assert palette.surface == "#e3e4e8"

    def test_missing_mode_is_inferred_from_background_luminance(self):
        light = Palette.from_colors({"background": "#fafafa", "foreground": "#111111",
                                     "dark_background": "#eeeeee"})
        dark = Palette.from_colors({"background": "#101010", "foreground": "#eeeeee",
                                    "lighter_background": "#202020"})
        assert light.surface == "#eeeeee"
        assert dark.surface == "#202020"

    def test_optional_colors_fall_back_to_the_essentials(self):
        palette = Palette.from_colors({"background": "#101010", "foreground": "#eeeeee"})
        assert palette == Palette(
            background="#101010",
            surface="#101010",
            foreground="#eeeeee",
            accent="#eeeeee",
            muted="#eeeeee",
        )

    def test_missing_background_is_rejected(self):
        with pytest.raises(ValueError, match="lacks 'background'"):
            Palette.from_colors({"foreground": "#eeeeee"})

    def test_non_hex_colour_is_rejected(self):
        with pytest.raises(ValueError, match="accent"):
            Palette.from_colors(
                {"background": "#101010", "foreground": "#eeeeee", "accent": "teal"}
            )


class TestGeneratingCss:
    palette = Palette.from_colors(parse_colors(DARK_THEME))

    def test_maps_the_palette_onto_gtk_named_colors(self):
        css = palette_css(self.palette, rounding=None)
        assert "@define-color theme_bg_color #282828;" in css
        assert "@define-color theme_base_color #3c3836;" in css
        assert "@define-color theme_selected_bg_color #7daea3;" in css
        assert "font-family: monospace" in css

    def test_applies_hyprland_rounding_when_known(self):
        assert "border-radius: 6px" in palette_css(self.palette, rounding=6)

    def test_keeps_the_default_rounding_when_unknown(self):
        assert "border-radius" not in palette_css(self.palette, rounding=None)


class TestLoadingTheActiveTheme:
    @pytest.fixture(autouse=True)
    def isolated_state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
        self.theme_dir = tmp_path / "omarchy" / "current" / "theme"
        self.theme_dir.mkdir(parents=True)

    def test_no_omarchy_theme_means_no_css(self):
        assert omarchy_theme_css() == ""

    def test_active_theme_becomes_css(self):
        (self.theme_dir / "colors.toml").write_text(DARK_THEME)
        assert "@define-color theme_fg_color #d4be98;" in omarchy_theme_css()

    def test_broken_theme_file_is_ignored(self):
        (self.theme_dir / "colors.toml").write_text('background = "nope"\n')
        assert omarchy_theme_css() == ""
