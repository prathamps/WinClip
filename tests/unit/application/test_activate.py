import pytest

from winclip.application import ActivateClip, CaptureClipboard
from winclip.domain import ClipNotFoundError, HistoryPolicy, Settings


@pytest.fixture
def capture(repo, settings_repo, clock, ids) -> CaptureClipboard:
    return CaptureClipboard(repo, settings_repo, HistoryPolicy(), clock, ids)


@pytest.fixture
def activate(repo, writer, injector, settings_repo, clock) -> ActivateClip:
    return ActivateClip(repo, writer, injector, settings_repo, clock)


class TestActivate:
    def test_puts_text_on_clipboard_and_pastes(self, capture, activate, writer, injector):
        item = capture.capture_text("paste me")
        result = activate.activate(item.id)
        assert writer.texts == ["paste me"]
        assert injector.paste_count == 1
        assert result.copied and result.pasted

    def test_puts_image_on_clipboard(self, capture, activate, writer):
        png = b"\x89PNG-data"
        item = capture.capture_image(png)
        activate.activate(item.id)
        assert writer.images == [png]

    def test_reports_copy_only_when_injection_unavailable(
        self, capture, activate, injector
    ):
        injector.available = False
        item = capture.capture_text("x")
        result = activate.activate(item.id)
        assert result.copied and not result.pasted

    def test_honours_auto_paste_off(self, capture, activate, injector, settings_repo):
        settings_repo.save(Settings(auto_paste=False))
        item = capture.capture_text("x")
        result = activate.activate(item.id)
        assert injector.paste_count == 0
        assert not result.pasted

    def test_activation_bumps_item_to_top(self, capture, activate, repo, clock):
        old = capture.capture_text("old")
        clock.advance(10)
        capture.capture_text("new")
        clock.advance(10)
        activate.activate(old.id)
        newest = max(repo.list_all(), key=lambda i: i.last_used_at)
        assert newest.id == old.id

    def test_missing_item_raises(self, activate):
        with pytest.raises(ClipNotFoundError):
            activate.activate("ghost")
