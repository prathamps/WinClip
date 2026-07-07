# WinClip Architecture

WinClip follows **hexagonal architecture** (ports & adapters). The goal:
the clipboard-history *behaviour* — capture, dedup, pin, evict, clear,
activate — is plain Python that can be tested in milliseconds and never
changes when we swap GTK versions, display servers, or storage engines.

## The hexagon

```
            DRIVING (who calls us)                 DRIVEN (whom we call)
 ┌──────────────────┐                                  ┌──────────────────┐
 │  GTK panel        │                                 │ SQLite repository │
 │  (window, rows)   │──┐                          ┌──▶│ (history.db)      │
 ├──────────────────┤  │   ┌──────────────────┐    │   ├──────────────────┤
 │  CLI              │──┼──▶│   APPLICATION    │────┼──▶│ JSON settings     │
 │  (winclip …)      │  │   │   use cases      │    │   ├──────────────────┤
 ├──────────────────┤  │   │                  │    ├──▶│ wl-copy / GTK     │
 │  Clipboard        │──┘   │  ┌────────────┐  │    │   │ clipboard writer  │
 │  monitors         │      │  │   DOMAIN   │  │    │   ├──────────────────┤
 │  (wl-paste watch, │      │  │ ClipItem   │  │    ├──▶│ paste injector    │
 │   X11 owner-      │      │  │ Settings   │  │    │   │ (ydotool/wtype/   │
 │   change)         │      │  │ Policy     │  │    │   │  xdotool)         │
 └──────────────────┘      │  └────────────┘  │    │   ├──────────────────┤
        driving ports ────▶│                  │────┘──▶│ clock, ids        │
    (application/ports/    └──────────────────┘        └──────────────────┘
         driving.py)         driven ports: application/ports/driven.py
```

Wiring happens in exactly one place: `winclip/bootstrap.py`, the
composition root.

## Layers and the dependency rule

| Layer | Path | May import |
|---|---|---|
| Domain | `winclip/domain/` | stdlib only |
| Application | `winclip/application/` | domain, stdlib |
| Adapters | `winclip/adapters/` | application ports, domain, anything |
| Composition root | `winclip/bootstrap.py` | everything |

Dependencies always point **inward**. The domain doesn't know the
application exists; the application doesn't know the adapters exist. This
is not aspirational — `tests/unit/test_architecture.py` parses every
import in the tree and CI fails on a violation (including any `gi`/GTK
import leaking into the core).

### Domain (`winclip/domain/`)

- `models.py` — `ClipItem` (immutable value object; content hash, pin
  state, timestamps), `ContentKind`, `Settings` (validated).
- `policy.py` — `HistoryPolicy`: the Windows-semantics rule book.
  Capturability (size caps, image toggle), eviction (LRU among unpinned
  only), clear-all (spares pinned), display order (MRU first).
- `errors.py` — domain exceptions.

### Application (`winclip/application/`)

- `ports/driving.py` — what the world may ask of us: `CapturesClipboard`,
  `QueriesHistory`, `ManagesHistory`, `ActivatesClip`, `ManagesSettings`.
- `ports/driven.py` — what we need from the world: `HistoryRepository`,
  `ClipboardWriter`, `PasteInjector`, `SettingsRepository`, `Clock`,
  `IdGenerator`. All `typing.Protocol`, so adapters need no inheritance.
- `use_cases.py` — one class per driving port. E.g. `CaptureClipboard`
  dedups by content hash (re-copy bumps the existing item), then trims
  per policy; `ActivateClip` writes to the clipboard, bumps recency, and
  attempts paste injection, reporting `ActivationResult(copied, pasted)`.

### Adapters (`winclip/adapters/`)

Driving (left side):

- `driving/cli.py` — argparse CLI; also the packaging entry point.
- `driving/gtk/` — the Win+V panel (GTK 3), preferences dialog, and the
  `Gtk.Application` shell that provides single-instance + D-Bus `toggle`.
- `driving/monitor/wayland.py` — `wl-paste --watch` as change notifier +
  one-shot fetches. Runs in a daemon thread.
- `driving/monitor/x11.py` — GTK clipboard `owner-change` signal on the
  main loop.

Driven (right side):

- `driven/sqlite_history.py` — single-file DB, WAL, lock-serialised for
  the monitor thread; images stored as BLOBs.
- `driven/json_settings.py` — forward/backward-compatible JSON with
  atomic writes.
- `driven/clipboard_writers.py` — `wl-copy` (Wayland) / GTK clipboard (X11).
- `driven/paste_injector.py` — probes ydotool/wtype/xdotool per session.
- `driven/system.py` — real clock and UUIDs.

## Key design decisions

1. **GTK is quarantined.** Only adapter modules import `gi`, and always
   lazily via the composition root or module-level guards. The whole test
   suite runs headless with no display server — CI needs nothing but
   Python.
2. **External processes over protocols.** On Wayland we deliberately
   shell out to `wl-clipboard` instead of speaking the data-control
   protocol ourselves: it's the battle-tested reference implementation,
   and a subprocess boundary is easy to reason about. The port hides this
   choice; a native implementation would be a drop-in adapter.
3. **Best-effort paste injection.** Key injection is compositor politics;
   the `PasteInjector` port returns a boolean and the UX degrades to
   copy + notification. The core never knows or cares which tool ran.
4. **Time and identity are ports.** `Clock` and `IdGenerator` make
   recency-based behaviour (dedup-bump, eviction order) deterministic in
   tests.
5. **Windows semantics live in one file.** Everything that makes WinClip
   "feel like Win+V" — dedup-to-top, pin immunity, clear-spares-pinned,
   LRU eviction, 4 MiB cap — is `domain/policy.py` + the `CaptureClipboard`
   use case, fully covered by fast tests.

## Adding an adapter

Want a GTK 4/libadwaita panel, a KDE Klipper-style monitor, or Postgres
storage?

1. Implement the relevant Protocol from `application/ports/`
   (no inheritance needed — just matching method signatures).
2. Wire it in `bootstrap.py` (and only there).
3. Add a contract test mirroring
   `tests/integration/test_sqlite_repository.py`.

Nothing in `domain/`, `application/`, or the other adapters changes.

## Testing strategy

- `tests/unit/domain/` — pure rule tests, no doubles needed.
- `tests/unit/application/` — use cases against in-memory fakes
  (`tests/conftest.py`); deterministic time via `FixedClock`.
- `tests/integration/` — adapter contract tests (SQLite, JSON settings)
  against real files in `tmp_path`.
- `tests/unit/test_architecture.py` — the dependency rule, enforced.

GTK widgets and the subprocess monitors are intentionally thin and are
exercised manually / by future e2e tooling rather than unit tests.
