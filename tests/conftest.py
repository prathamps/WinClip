"""Shared test doubles: in-memory implementations of the driven ports.

These fakes are what make the hexagonal core cheap to test — no
database, no display server, no subprocesses.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from winclip.domain import ClipItem, Settings


class InMemoryHistoryRepository:
    def __init__(self) -> None:
        self.items: dict[str, ClipItem] = {}

    def add(self, item: ClipItem) -> None:
        self.items[item.id] = item

    def get(self, clip_id: str) -> ClipItem | None:
        return self.items.get(clip_id)

    def find_by_hash(self, content_hash: str) -> ClipItem | None:
        for item in self.items.values():
            if item.content_hash == content_hash:
                return item
        return None

    def list_all(self) -> list[ClipItem]:
        return list(self.items.values())

    def update(self, item: ClipItem) -> None:
        assert item.id in self.items, "update of unknown item"
        self.items[item.id] = item

    def remove(self, clip_id: str) -> None:
        self.items.pop(clip_id, None)

    def remove_many(self, clip_ids: list[str]) -> None:
        for clip_id in clip_ids:
            self.items.pop(clip_id, None)


class InMemorySettingsRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def load(self) -> Settings:
        return self.settings

    def save(self, settings: Settings) -> None:
        self.settings = settings


class FakeClipboardWriter:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.images: list[bytes] = []

    def write_text(self, text: str) -> None:
        self.texts.append(text)

    def write_image(self, png_data: bytes) -> None:
        self.images.append(png_data)


class FakePasteInjector:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.paste_count = 0

    def paste(self) -> bool:
        self.paste_count += 1
        return self.available


class FixedClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int = 1) -> None:
        self.current += timedelta(seconds=seconds)


class SequentialIdGenerator:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"id-{self.counter:04d}"


@pytest.fixture
def repo() -> InMemoryHistoryRepository:
    return InMemoryHistoryRepository()


@pytest.fixture
def settings_repo() -> InMemorySettingsRepository:
    return InMemorySettingsRepository()


@pytest.fixture
def writer() -> FakeClipboardWriter:
    return FakeClipboardWriter()


@pytest.fixture
def injector() -> FakePasteInjector:
    return FakePasteInjector()


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def ids() -> SequentialIdGenerator:
    return SequentialIdGenerator()
