"""Trivial system adapters for the Clock and IdGenerator ports."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class UuidGenerator:
    def new_id(self) -> str:
        return uuid.uuid4().hex
