import pytest

from winclip.adapters.driving.gtk.thumbnails import ThumbnailCache, fit_within


class TestThumbnailCache:
    def test_empty_cache_misses(self):
        cache = ThumbnailCache(capacity=2)
        assert cache.get("nope") is None
        assert len(cache) == 0

    def test_put_then_get_returns_the_value(self):
        cache = ThumbnailCache(capacity=2)
        cache.put("a", "pixbuf-a")
        assert cache.get("a") == "pixbuf-a"
        assert "a" in cache

    def test_evicts_least_recently_used_beyond_capacity(self):
        cache = ThumbnailCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.put("c", 3)
        assert "b" not in cache
        assert cache.get("a") == 1
        assert cache.get("c") == 3

    def test_re_putting_a_key_refreshes_it(self):
        cache = ThumbnailCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)
        cache.put("c", 3)
        assert "b" not in cache
        assert cache.get("a") == 10

    def test_capacity_must_be_positive(self):
        with pytest.raises(ValueError):
            ThumbnailCache(capacity=0)


class TestFitWithin:
    def test_small_images_are_never_upscaled(self):
        assert fit_within(50, 40, 220, 110) == (50, 40)

    def test_wide_images_are_bounded_by_width(self):
        assert fit_within(2200, 550, 220, 110) == (220, 55)

    def test_tall_images_are_bounded_by_height(self):
        assert fit_within(300, 1100, 220, 110) == (30, 110)

    def test_never_collapses_to_zero(self):
        assert fit_within(10000, 1, 220, 110) == (220, 1)
