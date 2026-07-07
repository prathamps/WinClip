# Contributing to WinClip

Thanks for helping build a first-class clipboard experience for Linux!

## Getting started

```bash
git clone https://github.com/prathamps/WinClip.git
cd WinClip
make dev     # venv (with system PyGObject) + pytest + ruff
make test
make run     # run the daemon from the working tree
```

System packages you'll want locally: `python3-gi`, `gir1.2-gtk-3.0`,
`wl-clipboard` (Wayland), and optionally `wtype`/`ydotool`/`xdotool` for
paste injection.

## Ground rules

1. **Respect the hexagon.** Domain imports stdlib only; application
   imports domain only; technology lives in adapters; wiring lives in
   `bootstrap.py`. `tests/unit/test_architecture.py` enforces this — run
   it before pushing.
2. **Core changes come with tests.** Anything in `domain/` or
   `application/` is pure Python and cheap to test; PRs that change
   behaviour without tests will be asked to add them.
3. **New adapters follow the contract.** Implement the Protocol, wire it
   in `bootstrap.py`, add a contract test (see
   `tests/integration/test_sqlite_repository.py` as the template).
4. **Lint clean.** `make lint` (ruff) must pass; CI runs it on every PR.
5. **Keep the core dependency-free.** Runtime dependencies are stdlib +
   system PyGObject by design. If a feature seems to need a pip package,
   open an issue first.

## Good first contributions

- GTK 4 / libadwaita panel adapter (the port surface is small).
- KDE/Plasma and wlroots testing + fixes.
- File (`text/uri-list`) clipboard support.
- A settings page for the paste tool.
- Packaging: a proper `debian/` directory or Flatpak manifest.

## Reporting bugs

Please include your distro, desktop environment, session type
(`echo $XDG_SESSION_TYPE`), and the output of
`winclip -v daemon` while reproducing the issue.
