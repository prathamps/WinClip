"""JSON-file implementation of the SettingsRepository port.

Settings live at ``~/.config/winclip/settings.json``. Unknown keys are
ignored and missing keys fall back to defaults, so the file survives
version upgrades in both directions. Writes are atomic
(write-to-temp + rename).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from winclip.domain import Settings

log = logging.getLogger(__name__)

_FIELDS = {f.name for f in dataclasses.fields(Settings)}


class JsonSettingsRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Settings:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Settings()
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("could not read %s (%s); using defaults", self._path, exc)
            return Settings()
        known = {k: v for k, v in raw.items() if k in _FIELDS}
        try:
            return Settings(**known)
        except (TypeError, ValueError) as exc:
            log.warning("invalid settings in %s (%s); using defaults", self._path, exc)
            return Settings()

    def save(self, settings: Settings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(dataclasses.asdict(settings), indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._path)
