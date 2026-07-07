from datetime import datetime, timedelta, timezone

from winclip.domain import ClipItem, HistoryPolicy, Settings

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def text_item(i: int, pinned: bool = False) -> ClipItem:
    # Later index == more recently used.
    return ClipItem.from_text(
        f"id-{i}", f"content {i}", BASE + timedelta(minutes=i), pinned=pinned
    )


class TestCapturability:
    def test_accepts_normal_content(self):
        assert HistoryPolicy().is_capturable(100, is_image=False, settings=Settings())

    def test_rejects_empty_and_oversized(self):
        policy = HistoryPolicy()
        settings = Settings(max_item_bytes=10)
        assert not policy.is_capturable(0, is_image=False, settings=settings)
        assert not policy.is_capturable(11, is_image=False, settings=settings)
        assert policy.is_capturable(10, is_image=False, settings=settings)

    def test_respects_image_capture_toggle(self):
        policy = HistoryPolicy()
        off = Settings(capture_images=False)
        assert not policy.is_capturable(100, is_image=True, settings=off)
        assert policy.is_capturable(100, is_image=False, settings=off)


class TestEviction:
    def test_no_victims_under_cap(self):
        items = [text_item(i) for i in range(3)]
        assert HistoryPolicy().eviction_victims(items, Settings(max_items=5)) == []

    def test_evicts_least_recently_used_beyond_cap(self):
        items = [text_item(i) for i in range(5)]
        victims = HistoryPolicy().eviction_victims(items, Settings(max_items=3))
        assert sorted(v.id for v in victims) == ["id-0", "id-1"]

    def test_pinned_items_are_never_evicted_and_do_not_count(self):
        items = [text_item(i, pinned=True) for i in range(5)]
        items += [text_item(10 + i) for i in range(3)]
        victims = HistoryPolicy().eviction_victims(items, Settings(max_items=2))
        assert sorted(v.id for v in victims) == ["id-10"]


class TestClearAll:
    def test_clear_spares_pinned(self):
        items = [text_item(0), text_item(1, pinned=True), text_item(2)]
        cleared = HistoryPolicy().clearable(items)
        assert sorted(c.id for c in cleared) == ["id-0", "id-2"]


class TestDisplayOrder:
    def test_most_recently_used_first(self):
        items = [text_item(0), text_item(2), text_item(1)]
        ordered = HistoryPolicy().sort_for_display(items)
        assert [i.id for i in ordered] == ["id-2", "id-1", "id-0"]
