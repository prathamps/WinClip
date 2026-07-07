"""Contract tests for the SQLite adapter against the repository port."""

from datetime import datetime, timezone

import pytest

from winclip.adapters.driven.sqlite_history import SqliteHistoryRepository
from winclip.domain import ClipItem

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    repository = SqliteHistoryRepository(tmp_path / "history.db")
    yield repository
    repository.close()


class TestSqliteRoundtrip:
    def test_text_item_roundtrips(self, repo):
        item = ClipItem.from_text("id-1", "héllo wörld", NOW)
        repo.add(item)
        assert repo.get("id-1") == item

    def test_image_item_roundtrips(self, repo):
        blob = bytes(range(256)) * 100
        item = ClipItem.from_image("id-2", blob, NOW)
        repo.add(item)
        loaded = repo.get("id-2")
        assert loaded.image == blob
        assert loaded == item

    def test_find_by_hash(self, repo):
        item = ClipItem.from_text("id-1", "needle", NOW)
        repo.add(item)
        assert repo.find_by_hash(ClipItem.hash_text("needle")).id == "id-1"
        assert repo.find_by_hash("nope") is None

    def test_update_persists_pin_and_last_used(self, repo):
        item = ClipItem.from_text("id-1", "x", NOW)
        repo.add(item)
        later = datetime(2026, 2, 1, tzinfo=timezone.utc)
        repo.update(item.pinned_as(True).touched(later))
        loaded = repo.get("id-1")
        assert loaded.pinned is True
        assert loaded.last_used_at == later

    def test_remove_and_remove_many(self, repo):
        for i in range(3):
            repo.add(ClipItem.from_text(f"id-{i}", f"t{i}", NOW))
        repo.remove("id-0")
        repo.remove_many(["id-1", "id-2"])
        repo.remove_many([])  # no-op must not fail
        assert repo.list_all() == []

    def test_missing_item_is_none(self, repo):
        assert repo.get("ghost") is None

    def test_data_survives_reopen(self, tmp_path):
        path = tmp_path / "history.db"
        first = SqliteHistoryRepository(path)
        first.add(ClipItem.from_text("id-1", "persist me", NOW, pinned=True))
        first.close()

        second = SqliteHistoryRepository(path)
        loaded = second.get("id-1")
        second.close()
        assert loaded.text == "persist me"
        assert loaded.pinned is True
