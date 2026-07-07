import pytest

from winclip.application import CaptureClipboard
from winclip.domain import ContentKind, HistoryPolicy, Settings


@pytest.fixture
def capture(repo, settings_repo, clock, ids) -> CaptureClipboard:
    return CaptureClipboard(repo, settings_repo, HistoryPolicy(), clock, ids)


class TestTextCapture:
    def test_stores_new_text(self, capture, repo):
        item = capture.capture_text("hello world")
        assert item is not None
        assert repo.get(item.id).text == "hello world"

    def test_ignores_blank_text(self, capture, repo):
        assert capture.capture_text("   \n\t ") is None
        assert repo.list_all() == []

    def test_recopy_moves_existing_to_top_instead_of_duplicating(
        self, capture, repo, clock
    ):
        first = capture.capture_text("hello")
        clock.advance(60)
        capture.capture_text("other")
        clock.advance(60)
        second = capture.capture_text("hello")

        assert second.id == first.id
        assert len(repo.list_all()) == 2
        newest = max(repo.list_all(), key=lambda i: i.last_used_at)
        assert newest.text == "hello"

    def test_rejects_oversized_text(self, capture, repo, settings_repo):
        settings_repo.save(Settings(max_item_bytes=5))
        assert capture.capture_text("this is too long") is None
        assert repo.list_all() == []

    def test_trims_history_after_capture(self, capture, repo, settings_repo, clock):
        settings_repo.save(Settings(max_items=3))
        for i in range(5):
            capture.capture_text(f"item {i}")
            clock.advance(1)
        remaining = {i.text for i in repo.list_all()}
        assert remaining == {"item 2", "item 3", "item 4"}

    def test_trim_never_removes_pinned(self, capture, repo, settings_repo, clock):
        settings_repo.save(Settings(max_items=2))
        pinned = capture.capture_text("keep me")
        repo.update(pinned.pinned_as(True))
        for i in range(4):
            clock.advance(1)
            capture.capture_text(f"item {i}")
        texts = {i.text for i in repo.list_all()}
        assert "keep me" in texts
        assert len(texts) == 3  # pinned + 2 unpinned


class TestImageCapture:
    PNG = b"\x89PNG\r\n\x1a\n" + b"fake" * 10

    def test_stores_image(self, capture, repo):
        item = capture.capture_image(self.PNG)
        assert item is not None
        assert item.kind is ContentKind.IMAGE
        assert repo.get(item.id).image == self.PNG

    def test_respects_capture_images_setting(self, capture, repo, settings_repo):
        settings_repo.save(Settings(capture_images=False))
        assert capture.capture_image(self.PNG) is None
        assert repo.list_all() == []

    def test_recopy_of_same_image_deduplicates(self, capture, repo, clock):
        first = capture.capture_image(self.PNG)
        clock.advance(1)
        second = capture.capture_image(self.PNG)
        assert first.id == second.id
        assert len(repo.list_all()) == 1
