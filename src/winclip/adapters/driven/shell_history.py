"""CommandHistorySource implementation reading shell history files.

Supports the three common formats:

* bash  — ``~/.bash_history``: one command per line
* zsh   — ``~/.zsh_history`` / ``$HISTFILE``: plain lines or the
  extended ``: <epoch>:<duration>;command`` format (multiline commands
  continue with a trailing backslash)
* fish  — ``~/.local/share/fish/fish_history``: YAML-ish
  ``- cmd: <command>`` entries

Reading is on demand and capped to the tail of each file, so even
multi-megabyte histories stay cheap. Parsed results are cached per
file and reused until the file's size or mtime changes, so opening the
panel repeatedly does not re-read anything. Files are merged
bash → zsh → fish, each oldest-first; note that bash only flushes
history on shell exit unless ``PROMPT_COMMAND='history -a'`` is set.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_LINES_PER_FILE = 5000
_MAX_TAIL_BYTES = 1024 * 1024  # read at most the last 1 MiB of a file

FileStamp = tuple[int, int]
Parser = Callable[[list[str]], list[str]]


class ShellHistorySource:
    def __init__(self, home: Path | None = None) -> None:
        self._home = home or Path.home()
        self._cache: dict[Path, tuple[FileStamp, list[str]]] = {}

    def recent_commands(self) -> list[str]:
        commands: list[str] = []
        commands += self._parsed(self._home / ".bash_history", _parse_bash)
        commands += self._parsed(self._zsh_histfile(), _parse_zsh)
        commands += self._parsed(
            self._home / ".local" / "share" / "fish" / "fish_history", _parse_fish
        )
        return commands

    def _parsed(self, path: Path, parser: Parser) -> list[str]:
        stamp = _stamp_of(path)
        if stamp is None:
            self._cache.pop(path, None)
            return []
        cached = self._cache.get(path)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        commands = parser(_tail_lines(path))
        self._cache[path] = (stamp, commands)
        return commands

    def _zsh_histfile(self) -> Path:
        histfile = os.environ.get("HISTFILE", "")
        if histfile and "zsh" in histfile.lower():
            return Path(histfile).expanduser()
        return self._home / ".zsh_history"


def _parse_bash(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() and not line.startswith("#")]


def _parse_zsh(lines: list[str]) -> list[str]:
    commands: list[str] = []
    continuation = False
    for line in lines:
        if continuation:
            continuation = line.endswith("\\")
            continue
        if line.startswith(": ") and ";" in line:
            line = line.split(";", 1)[1]
        continuation = line.endswith("\\")
        line = line.rstrip("\\").strip()
        if line:
            commands.append(line)
    return commands


def _parse_fish(lines: list[str]) -> list[str]:
    commands: list[str] = []
    for line in lines:
        if line.startswith("- cmd: "):
            command = line[len("- cmd: ") :].strip()
            if command:
                commands.append(command)
    return commands


def _stamp_of(path: Path) -> FileStamp | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _tail_lines(path: Path) -> list[str]:
    """The last ~1 MiB of a file as decoded lines, oldest first."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > _MAX_TAIL_BYTES:
                fh.seek(size - _MAX_TAIL_BYTES)
                fh.readline()  # drop the probably-partial first line
            data = fh.read()
    except OSError:
        return []
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[-_MAX_LINES_PER_FILE:]
