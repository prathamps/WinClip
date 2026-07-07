"""CommandHistorySource implementation reading shell history files.

Supports the three common formats:

* bash  — ``~/.bash_history``: one command per line
* zsh   — ``~/.zsh_history`` / ``$HISTFILE``: plain lines or the
  extended ``: <epoch>:<duration>;command`` format (multiline commands
  continue with a trailing backslash)
* fish  — ``~/.local/share/fish/fish_history``: YAML-ish
  ``- cmd: <command>`` entries

Reading is on demand and capped to the tail of each file, so even
multi-megabyte histories stay cheap. Files are merged bash → zsh →
fish, each oldest-first; note that bash only flushes history on shell
exit unless ``PROMPT_COMMAND='history -a'`` is set.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_LINES_PER_FILE = 5000
_MAX_TAIL_BYTES = 1024 * 1024  # read at most the last 1 MiB of a file


class ShellHistorySource:
    def __init__(self, home: Path | None = None) -> None:
        self._home = home or Path.home()

    def recent_commands(self) -> list[str]:
        commands: list[str] = []
        commands += self._read_bash(self._home / ".bash_history")
        commands += self._read_zsh(self._zsh_histfile())
        commands += self._read_fish(
            self._home / ".local" / "share" / "fish" / "fish_history"
        )
        return commands

    # -- per-shell parsers ---------------------------------------------

    @staticmethod
    def _read_bash(path: Path) -> list[str]:
        return [
            line
            for line in _tail_lines(path)
            if line.strip() and not line.startswith("#")
        ]

    @staticmethod
    def _read_zsh(path: Path) -> list[str]:
        commands: list[str] = []
        continuation = False
        for line in _tail_lines(path):
            if continuation:
                # Continuation of a multiline command; keep only its
                # first line for display purposes.
                continuation = line.endswith("\\")
                continue
            if line.startswith(": ") and ";" in line:
                # Extended format: ": 1699999999:0;git status"
                line = line.split(";", 1)[1]
            continuation = line.endswith("\\")
            line = line.rstrip("\\").strip()
            if line:
                commands.append(line)
        return commands

    @staticmethod
    def _read_fish(path: Path) -> list[str]:
        commands: list[str] = []
        for line in _tail_lines(path):
            if line.startswith("- cmd: "):
                command = line[len("- cmd: ") :].strip()
                if command:
                    commands.append(command)
        return commands

    def _zsh_histfile(self) -> Path:
        histfile = os.environ.get("HISTFILE", "")
        if histfile and "zsh" in histfile.lower():
            return Path(histfile).expanduser()
        return self._home / ".zsh_history"


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
