"""Command-history rules: turning raw shell history into a browsable,
tool-grouped list.

Raw history arrives as plain command strings ordered oldest → newest.
This module decides everything else — which token identifies the tool,
how duplicates collapse, and how tools are ranked. Ranking uses a
zoxide-style *frecency* blend: tools you use often rank high, but a
burst of recent use beats stale volume.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

# Wrappers that defer to the "real" command that follows them.
_WRAPPERS = {"sudo", "doas", "env", "nohup", "time", "command", "builtin", "exec"}
# Shell noise not worth grouping under.
_IGNORED_TOOLS = {"cd", "ls", "ll", "la", "pwd", "exit", "clear", "history", "which"}
_RECENT_WINDOW = 100  # commands considered "recent" for the frecency boost


@dataclass(frozen=True)
class ToolUsage:
    tool: str
    count: int
    score: float


@dataclass(frozen=True)
class CommandEntry:
    command: str
    tool: str


class CommandHistoryPolicy:
    """Pure grouping/ranking logic — no files, no processes."""

    def entries(self, raw_history: list[str]) -> list[CommandEntry]:
        """Parsed, de-duplicated entries, most recent first.

        Duplicate commands keep only their most recent occurrence,
        mirroring how the clipboard history bumps re-copied items.
        """
        seen: set[str] = set()
        result: list[CommandEntry] = []
        for line in reversed(raw_history):
            command = line.strip()
            if not command or command in seen:
                continue
            tool = self.tool_of(command)
            if tool is None:
                continue
            seen.add(command)
            result.append(CommandEntry(command=command, tool=tool))
        return result

    def tool_of(self, command: str) -> str | None:
        """The tool a command belongs to: its first meaningful token."""
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:  # unbalanced quotes etc.
            tokens = command.split()
        for token in tokens:
            if "=" in token and not token.startswith(("/", ".")):
                continue  # VAR=value prefix
            if token.startswith("-"):
                continue  # a wrapper's flag (e.g. sudo -E)
            name = token.rsplit("/", 1)[-1]
            if name in _WRAPPERS:
                continue
            if name in _IGNORED_TOOLS or not name or not name[0].isalnum():
                return None
            return name
        return None

    def tools(self, raw_history: list[str]) -> list[ToolUsage]:
        """Tools ranked by frecency: usage count + a recency boost."""
        entries = self.entries(raw_history)
        counts: dict[str, int] = {}
        recent_hits: dict[str, int] = {}
        for index, entry in enumerate(entries):
            counts[entry.tool] = counts.get(entry.tool, 0) + 1
            if index < _RECENT_WINDOW:
                recent_hits[entry.tool] = recent_hits.get(entry.tool, 0) + 1
        usages = [
            ToolUsage(
                tool=tool,
                count=count,
                score=count + 2.0 * recent_hits.get(tool, 0),
            )
            for tool, count in counts.items()
        ]
        return sorted(usages, key=lambda u: (-u.score, u.tool))

    def commands_for(
        self, raw_history: list[str], tool: str | None, query: str = ""
    ) -> list[CommandEntry]:
        """Entries filtered by tool (None = all) and search query."""
        needle = query.lower()
        return [
            e
            for e in self.entries(raw_history)
            if (tool is None or e.tool == tool)
            and (not needle or needle in e.command.lower())
        ]
