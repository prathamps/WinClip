from datetime import datetime, timezone

import pytest

from winclip.domain import ClipItem, ContentKind, Settings

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestClipItem:
    def test_text_item_carries_content_and_hash(self):
        item = ClipItem.from_text("a", "hello", NOW)
        assert item.kind is ContentKind.TEXT
        assert item.text == "hello"
        assert item.content_hash == ClipItem.hash_text("hello")

    def test_identical_text_hashes_identically(self):
        assert ClipItem.hash_text("x") == ClipItem.hash_text("x")
        assert ClipItem.hash_text("x") != ClipItem.hash_text("y")

    def test_text_and_image_of_same_bytes_hash_differently(self):
        assert ClipItem.hash_text("abc") != ClipItem.hash_image(b"abc")

    def test_touched_updates_last_used_but_not_created(self):
        item = ClipItem.from_text("a", "hello", NOW)
        later = datetime(2026, 1, 2, tzinfo=timezone.utc)
        touched = item.touched(later)
        assert touched.last_used_at == later
        assert touched.created_at == NOW

    def test_pinned_as_toggles_pin_state(self):
        item = ClipItem.from_text("a", "hello", NOW)
        assert item.pinned_as(True).pinned is True
        assert item.pinned_as(True).pinned_as(False).pinned is False

    def test_size_bytes_counts_utf8_text(self):
        item = ClipItem.from_text("a", "héllo", NOW)
        assert item.size_bytes == len("héllo".encode())

    def test_preview_collapses_whitespace_and_truncates(self):
        item = ClipItem.from_text("a", "  line one\n\n  line two  ", NOW)
        assert item.preview() == "line one line two"
        long_item = ClipItem.from_text("b", "x" * 500, NOW)
        assert len(long_item.preview(100)) == 100
        assert long_item.preview(100).endswith("…")

    def test_image_preview_shows_size(self):
        item = ClipItem.from_image("a", b"\x89PNG" * 1024, NOW)
        assert "Image" in item.preview()
        assert "KiB" in item.preview()

    def test_matches_is_case_insensitive_substring(self):
        item = ClipItem.from_text("a", "Hello World", NOW)
        assert item.matches("world")
        assert item.matches("")
        assert not item.matches("mars")

    def test_images_never_match_text_queries(self):
        item = ClipItem.from_image("a", b"data", NOW)
        assert not item.matches("data")
        assert item.matches("")


class TestSettings:
    def test_defaults_are_windows_like(self):
        s = Settings()
        assert s.max_items == 50
        assert s.max_item_bytes == 4 * 1024 * 1024
        assert s.capture_images is True

    @pytest.mark.parametrize("field", ["max_items", "max_item_bytes"])
    def test_rejects_non_positive_limits(self, field):
        with pytest.raises(ValueError):
            Settings(**{field: 0})

    def test_rejects_unknown_paste_tool(self):
        with pytest.raises(ValueError):
            Settings(paste_tool="telepathy")

    def test_rejects_implausible_panel_sizes(self):
        with pytest.raises(ValueError):
            Settings(panel_width=100)
        with pytest.raises(ValueError):
            Settings(panel_height=0)
        assert Settings(panel_width=500, panel_height=700).panel_width == 500
