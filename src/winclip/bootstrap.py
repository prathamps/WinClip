"""Composition root: the only place where core and adapters meet.

Everything else in the codebase depends inward (adapters -> ports ->
domain); this module wires the concrete adapters into the use cases
based on the runtime environment (Wayland vs X11, XDG directories).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from winclip.adapters.driven.json_settings import JsonSettingsRepository
from winclip.adapters.driven.paste_injector import CommandPasteInjector
from winclip.adapters.driven.shell_history import ShellHistorySource
from winclip.adapters.driven.sqlite_history import SqliteHistoryRepository
from winclip.adapters.driven.system import SystemClock, UuidGenerator
from winclip.application import (
    ActivateClip,
    ActivateSnippet,
    CaptureClipboard,
    ManageHistory,
    ManageSettings,
    QueryCommands,
    QueryHistory,
)
from winclip.domain import CommandHistoryPolicy, HistoryPolicy

log = logging.getLogger(__name__)


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME", "~/.local/share")
    return Path(base).expanduser() / "winclip"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return Path(base).expanduser() / "winclip"


def session_type() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "x11").lower()


@dataclass
class Container:
    """All wired use cases plus lifecycle hooks."""

    capture: CaptureClipboard
    query: QueryHistory
    manage: ManageHistory
    activate: ActivateClip
    activate_snippet: ActivateSnippet
    query_commands: QueryCommands
    settings: ManageSettings
    monitor: SupportsMonitor
    _closers: list = field(default_factory=list)

    def shutdown(self) -> None:
        self.monitor.stop()
        for close in self._closers:
            close()


class SupportsMonitor:
    """Structural stand-in for type hints; monitors provide start/stop."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


class NullMonitor:
    """Used by CLI commands that only read the database."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def build_core(with_monitor: bool = True) -> Container:
    repo = SqliteHistoryRepository(data_dir() / "history.db")
    settings_repo = JsonSettingsRepository(config_dir() / "settings.json")
    policy = HistoryPolicy()
    clock = SystemClock()
    ids = UuidGenerator()
    session = session_type()

    writer = _clipboard_writer(session)
    injector = CommandPasteInjector(
        session_type=session,
        preferred_tool=settings_repo.load().paste_tool,
    )

    capture = CaptureClipboard(repo, settings_repo, policy, clock, ids)
    query = QueryHistory(repo, policy)
    manage = ManageHistory(repo, policy)
    activate = ActivateClip(
        repository=repo,
        writer=writer,
        injector=injector,
        settings_repo=settings_repo,
        clock=clock,
    )
    activate_snippet = ActivateSnippet(
        writer=writer, injector=injector, settings_repo=settings_repo
    )
    query_commands = QueryCommands(
        source=ShellHistorySource(),
        policy=CommandHistoryPolicy(),
        settings_repo=settings_repo,
    )
    settings = ManageSettings(settings_repo)

    monitor: SupportsMonitor = NullMonitor()
    if with_monitor:
        monitor = _monitor(session, capture)

    return Container(
        capture=capture,
        query=query,
        manage=manage,
        activate=activate,
        activate_snippet=activate_snippet,
        query_commands=query_commands,
        settings=settings,
        monitor=monitor,
        _closers=[repo.close],
    )


def _clipboard_writer(session: str):
    if session == "wayland":
        from winclip.adapters.driven.clipboard_writers import WlClipboardWriter

        return WlClipboardWriter()
    from winclip.adapters.driven.clipboard_writers import GtkClipboardWriter

    return GtkClipboardWriter()


def _monitor(session: str, capture: CaptureClipboard) -> SupportsMonitor:
    if session == "wayland":
        from winclip.adapters.driving.monitor.wayland import WaylandClipboardMonitor

        return WaylandClipboardMonitor(capture)
    from winclip.adapters.driving.monitor.x11 import X11ClipboardMonitor

    return X11ClipboardMonitor(capture)
