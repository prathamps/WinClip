"""Application use cases.

Each class implements one driving port. Use cases orchestrate the
domain (models + policy) and the driven ports; they contain no
technology-specific code and no UI logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from winclip.domain import (
    ClipItem,
    ClipNotFoundError,
    CommandEntry,
    CommandHistoryPolicy,
    ContentKind,
    HistoryPolicy,
    Settings,
    ToolUsage,
)

from .ports.driven import (
    ClipboardWriter,
    Clock,
    CommandHistorySource,
    HistoryRepository,
    IdGenerator,
    PasteInjector,
    SettingsRepository,
)

log = logging.getLogger(__name__)


class CaptureClipboard:
    """Record what just landed on the system clipboard.

    Re-copied content is de-duplicated: the existing item is bumped to
    the top of the history rather than stored twice. After every
    capture the history is trimmed according to policy.
    """

    def __init__(
        self,
        repository: HistoryRepository,
        settings_repo: SettingsRepository,
        policy: HistoryPolicy,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._repo = repository
        self._settings_repo = settings_repo
        self._policy = policy
        self._clock = clock
        self._ids = ids

    def capture_text(self, text: str) -> ClipItem | None:
        if not text.strip():
            return None
        settings = self._settings_repo.load()
        size = len(text.encode("utf-8"))
        if not self._policy.is_capturable(size, is_image=False, settings=settings):
            log.debug("skipping text capture (%d bytes)", size)
            return None
        return self._store(
            content_hash=ClipItem.hash_text(text),
            build=lambda item_id, now: ClipItem.from_text(item_id, text, now),
            settings=settings,
        )

    def capture_image(self, png_data: bytes) -> ClipItem | None:
        settings = self._settings_repo.load()
        if not self._policy.is_capturable(
            len(png_data), is_image=True, settings=settings
        ):
            log.debug("skipping image capture (%d bytes)", len(png_data))
            return None
        return self._store(
            content_hash=ClipItem.hash_image(png_data),
            build=lambda item_id, now: ClipItem.from_image(item_id, png_data, now),
            settings=settings,
        )

    def _store(self, content_hash, build, settings: Settings) -> ClipItem:
        now = self._clock.now()
        existing = self._repo.find_by_hash(content_hash)
        if existing is not None:
            item = existing.touched(now)
            self._repo.update(item)
        else:
            item = build(self._ids.new_id(), now)
            self._repo.add(item)
        self._trim(settings)
        return item

    def _trim(self, settings: Settings) -> None:
        victims = self._policy.eviction_victims(self._repo.list_all(), settings)
        if victims:
            self._repo.remove_many([v.id for v in victims])


class QueryHistory:
    """Read-side of the panel: list and search."""

    def __init__(self, repository: HistoryRepository, policy: HistoryPolicy) -> None:
        self._repo = repository
        self._policy = policy

    def list_items(self) -> list[ClipItem]:
        return self._policy.sort_for_display(self._repo.list_all())

    def search(self, query: str) -> list[ClipItem]:
        return [i for i in self.list_items() if i.matches(query)]


class ManageHistory:
    """Pin, unpin, delete, and clear."""

    def __init__(self, repository: HistoryRepository, policy: HistoryPolicy) -> None:
        self._repo = repository
        self._policy = policy

    def toggle_pin(self, clip_id: str) -> ClipItem:
        item = self._require(clip_id)
        updated = item.pinned_as(not item.pinned)
        self._repo.update(updated)
        return updated

    def delete(self, clip_id: str) -> None:
        self._require(clip_id)
        self._repo.remove(clip_id)

    def clear(self) -> int:
        """Remove everything except pinned items. Returns removed count."""
        victims = self._policy.clearable(self._repo.list_all())
        self._repo.remove_many([v.id for v in victims])
        return len(victims)

    def _require(self, clip_id: str) -> ClipItem:
        item = self._repo.get(clip_id)
        if item is None:
            raise ClipNotFoundError(clip_id)
        return item


@dataclass(frozen=True)
class ActivationResult:
    copied: bool
    pasted: bool


class ActivateClip:
    """The user picked an item: put it on the clipboard and paste it.

    Pasting is best-effort — on setups without a key-injection tool the
    item is still copied and the user pastes manually, which is the
    graceful degradation path on locked-down Wayland compositors.
    """

    def __init__(
        self,
        repository: HistoryRepository,
        writer: ClipboardWriter,
        injector: PasteInjector,
        settings_repo: SettingsRepository,
        clock: Clock,
    ) -> None:
        self._repo = repository
        self._writer = writer
        self._injector = injector
        self._settings_repo = settings_repo
        self._clock = clock

    def activate(self, clip_id: str) -> ActivationResult:
        item = self._repo.get(clip_id)
        if item is None:
            raise ClipNotFoundError(clip_id)

        if item.kind is ContentKind.TEXT:
            self._writer.write_text(item.text or "")
        else:
            self._writer.write_image(item.image or b"")

        self._repo.update(item.touched(self._clock.now()))

        pasted = False
        if self._settings_repo.load().auto_paste:
            pasted = self._injector.paste()
        return ActivationResult(copied=True, pasted=pasted)


class ActivateSnippet:
    """Put arbitrary text (an emoji, symbol, or command) on the
    clipboard and paste it.

    The clipboard monitor will observe the resulting clipboard change
    and record it in the history like any other copy — no special
    bookkeeping needed here.
    """

    def __init__(
        self,
        writer: ClipboardWriter,
        injector: PasteInjector,
        settings_repo: SettingsRepository,
    ) -> None:
        self._writer = writer
        self._injector = injector
        self._settings_repo = settings_repo

    def activate_text(self, text: str) -> ActivationResult:
        self._writer.write_text(text)
        pasted = False
        if self._settings_repo.load().auto_paste:
            pasted = self._injector.paste()
        return ActivationResult(copied=True, pasted=pasted)


class QueryCommands:
    """Browse shell history grouped by tool (docker, npm, kubectl, …).

    Honours the ``show_commands`` privacy setting: when disabled, the
    source is never consulted and everything reads as empty.
    """

    def __init__(
        self,
        source: CommandHistorySource,
        policy: CommandHistoryPolicy,
        settings_repo: SettingsRepository,
    ) -> None:
        self._source = source
        self._policy = policy
        self._settings_repo = settings_repo

    def tools(self) -> list[ToolUsage]:
        if not self._settings_repo.load().show_commands:
            return []
        return self._policy.tools(self._source.recent_commands())

    def commands(self, tool: str | None, query: str = "") -> list[CommandEntry]:
        if not self._settings_repo.load().show_commands:
            return []
        return self._policy.commands_for(self._source.recent_commands(), tool, query)


class ManageSettings:
    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def get_settings(self) -> Settings:
        return self._settings_repo.load()

    def update_settings(self, settings: Settings) -> Settings:
        self._settings_repo.save(settings)
        return settings
