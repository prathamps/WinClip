import pytest

from winclip.application import CaptureClipboard, ManageHistory, QueryHistory
from winclip.domain import ClipNotFoundError, HistoryPolicy


@pytest.fixture
def capture(repo, settings_repo, clock, ids) -> CaptureClipboard:
    return CaptureClipboard(repo, settings_repo, HistoryPolicy(), clock, ids)


@pytest.fixture
def query(repo) -> QueryHistory:
    return QueryHistory(repo, HistoryPolicy())


@pytest.fixture
def manage(repo) -> ManageHistory:
    return ManageHistory(repo, HistoryPolicy())


class TestQuery:
    def test_lists_most_recent_first(self, capture, query, clock):
        capture.capture_text("first")
        clock.advance(1)
        capture.capture_text("second")
        assert [i.text for i in query.list_items()] == ["second", "first"]

    def test_search_filters_by_substring(self, capture, query):
        capture.capture_text("the quick brown fox")
        capture.capture_text("lazy dog")
        results = query.search("QUICK")
        assert [i.text for i in results] == ["the quick brown fox"]

    def test_empty_search_returns_everything(self, capture, query):
        capture.capture_text("a")
        capture.capture_text("b")
        assert len(query.search("")) == 2


class TestManage:
    def test_toggle_pin_flips_state(self, capture, manage, repo):
        item = capture.capture_text("pin me")
        assert manage.toggle_pin(item.id).pinned is True
        assert manage.toggle_pin(item.id).pinned is False
        assert repo.get(item.id).pinned is False

    def test_delete_removes_item(self, capture, manage, repo):
        item = capture.capture_text("bye")
        manage.delete(item.id)
        assert repo.get(item.id) is None

    def test_operations_on_missing_items_raise(self, manage):
        with pytest.raises(ClipNotFoundError):
            manage.toggle_pin("ghost")
        with pytest.raises(ClipNotFoundError):
            manage.delete("ghost")

    def test_clear_removes_unpinned_and_reports_count(
        self, capture, manage, repo, clock
    ):
        keeper = capture.capture_text("keeper")
        manage.toggle_pin(keeper.id)
        clock.advance(1)
        capture.capture_text("one")
        capture.capture_text("two")

        assert manage.clear() == 2
        assert [i.text for i in repo.list_all()] == ["keeper"]
