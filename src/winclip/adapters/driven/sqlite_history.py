"""SQLite implementation of the HistoryRepository port.

A single-file database keeps the history (including image blobs)
self-contained under ``~/.local/share/winclip``. The connection is
shared between the GTK main loop and the clipboard-monitor thread, so
every access is serialised with a lock.

Listing never reads image blobs: the panel only needs metadata and
the byte count, and fetches a single image on demand via
:meth:`image_of`.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from winclip.domain import ClipItem, ContentKind

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    text_content  TEXT,
    image_content BLOB,
    content_hash  TEXT NOT NULL,
    pinned        INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    last_used_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clips_hash ON clips(content_hash);
CREATE INDEX IF NOT EXISTS idx_clips_last_used ON clips(last_used_at);
"""

_ITEM_COLUMNS = (
    "id, kind, text_content, content_hash, pinned, created_at, last_used_at,"
    " COALESCE(length(image_content), 0)"
)
_SELECT_METADATA = f"SELECT {_ITEM_COLUMNS}, NULL FROM clips"
_SELECT_FULL = f"SELECT {_ITEM_COLUMNS}, image_content FROM clips"

_VACUUM_FREE_PAGE_RATIO = 0.25


class SqliteHistoryRepository:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def add(self, item: ClipItem) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO clips (id, kind, text_content, image_content,"
                " content_hash, pinned, created_at, last_used_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.kind.value,
                    item.text,
                    item.image,
                    item.content_hash,
                    int(item.pinned),
                    item.created_at.isoformat(),
                    item.last_used_at.isoformat(),
                ),
            )

    def get(self, clip_id: str) -> ClipItem | None:
        with self._lock:
            row = self._conn.execute(
                f"{_SELECT_FULL} WHERE id = ?", (clip_id,)
            ).fetchone()
        return self._to_item(row) if row else None

    def find_by_hash(self, content_hash: str) -> ClipItem | None:
        with self._lock:
            row = self._conn.execute(
                f"{_SELECT_METADATA} WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            ).fetchone()
        return self._to_item(row) if row else None

    def list_all(self) -> list[ClipItem]:
        with self._lock:
            rows = self._conn.execute(_SELECT_METADATA).fetchall()
        return [self._to_item(row) for row in rows]

    def image_of(self, clip_id: str) -> bytes | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT image_content FROM clips WHERE id = ?", (clip_id,)
            ).fetchone()
        return row[0] if row else None

    def update(self, item: ClipItem) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE clips SET pinned = ?, last_used_at = ? WHERE id = ?",
                (int(item.pinned), item.last_used_at.isoformat(), item.id),
            )

    def remove(self, clip_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))

    def remove_many(self, clip_ids: list[str]) -> None:
        if not clip_ids:
            return
        placeholders = ",".join("?" * len(clip_ids))
        with self._lock, self._conn:
            self._conn.execute(
                f"DELETE FROM clips WHERE id IN ({placeholders})", clip_ids
            )

    def maintain(self) -> None:
        """One-off startup housekeeping: durable-enough sync, a trimmed
        WAL, and compaction when deleted blobs have bloated the file."""
        with self._lock:
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            if self._free_page_ratio() > _VACUUM_FREE_PAGE_RATIO:
                self._conn.execute("VACUUM")
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def _free_page_ratio(self) -> float:
        page_count = self._conn.execute("PRAGMA page_count").fetchone()[0]
        freelist = self._conn.execute("PRAGMA freelist_count").fetchone()[0]
        return freelist / page_count if page_count else 0.0

    def page_count(self) -> int:
        with self._lock:
            return self._conn.execute("PRAGMA page_count").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.close()

    @staticmethod
    def _to_item(row: tuple) -> ClipItem:
        (
            clip_id,
            kind,
            text,
            content_hash,
            pinned,
            created_at,
            last_used_at,
            image_size,
            image,
        ) = row
        return ClipItem(
            id=clip_id,
            kind=ContentKind(kind),
            text=text,
            image=image,
            image_size=image_size,
            content_hash=content_hash,
            pinned=bool(pinned),
            created_at=datetime.fromisoformat(created_at),
            last_used_at=datetime.fromisoformat(last_used_at),
        )
