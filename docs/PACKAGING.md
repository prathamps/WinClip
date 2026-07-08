# Packaging & Distribution

How WinClip reaches users, and the trade-offs behind each channel.
WinClip is unusually easy to package — the runtime is the Python
standard library plus distro packages (`python3-gi`, `gir1.2-gtk-3.0`,
`wl-clipboard`) — but unusually hard to sandbox, which shapes the
strategy below.

## Channels we ship today

### 1. GitHub Releases: `.deb` + wheel/sdist (automated)

Pushing a tag `vX.Y.Z` runs `.github/workflows/release.yml`, which:

1. runs lint + tests,
2. verifies the tag matches `pyproject.toml`'s version,
3. builds the wheel, sdist, and a `.deb` (`scripts/build-deb.sh`),
4. creates a GitHub Release with all three attached.

The `.deb` is built with plain `dpkg-deb`: pure-Python payload in
`/usr/lib/python3/dist-packages`, a `/usr/bin/winclip` launcher, the
desktop entry, and a systemd **user** unit in `/usr/lib/systemd/user`.
Users install and opt in per account:

```bash
sudo apt install ./winclip_X.Y.Z_all.deb
systemctl --user enable --now winclip.service
```

### 2. PyPI → `pipx install winclip`

The release workflow publishes to PyPI when the repository variable
`PUBLISH_PYPI` is `true`. One-time setup:

1. On pypi.org, create the `winclip` project and add a **trusted
   publisher**: this repo, workflow `release.yml`, environment `pypi`
   (no API token needed — the workflow uses OIDC).
2. In the repo settings, create the `pypi` environment and set the
   repository variable `PUBLISH_PYPI=true`.

Users then need only:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 wl-clipboard pipx
pipx install --system-site-packages winclip
```

(`--system-site-packages` matters: PyGObject comes from apt, not pip.)

### 3. From source: `scripts/install.sh`

The full-service path for this repo's users: installs apt deps, the
CLI, the systemd unit, and binds Super+V on GNOME/COSMIC. Best
experience, Debian-family only.

## Channels worth adding later

| Channel | Effort | Notes |
|---|---|---|
| **AUR** (Arch) | Low | A `PKGBUILD` over the sdist; community can own it. Arch deps: `python-gobject gtk3 wl-clipboard`. |
| **Official Debian/Ubuntu** | High | Proper `debian/` dir with `dh-python`/`pybuild`, an ITP bug, a sponsor, and the freeze calendar. The current `.deb` is a stepping stone, not a substitute. |
| **PPA / OBS repo** | Medium | Same `debian/` work, but self-served; gives users `apt upgrade`. |
| **Flatpak** | High, degraded | See below. |
| **Snap** | High, degraded | Needs classic confinement (store review) for the same reasons as Flatpak. |

### Why Flatpak/Snap are a poor fit (today)

A clipboard *manager* needs three things sandboxes are designed to
prevent:

1. **Reading the clipboard in the background.** Portals only expose
   clipboard content to focused windows; `wl-paste --watch` relies on
   the data-control protocol, which sandboxes don't broker.
2. **Synthesising keystrokes** (the auto-paste). `ydotool` needs
   `/dev/uinput`; `wtype` needs an unbrokered Wayland virtual-keyboard
   protocol.
3. **Autostarting a daemon** tied to the session.

A Flatpak with holes punched (`--socket=wayland --talk-name=...
--device=all --filesystem=...`) stops being meaningfully sandboxed and
still breaks on portals-only systems. GPaste and friends made the same
call: native packaging first. Revisit if/when the clipboard portal
grows history/data-control support.

## Release checklist

1. Bump the version in **both** `pyproject.toml` and
   `src/winclip/__init__.py` (the pre-commit hook enforces they match).
2. Update `README.md` if user-facing behaviour changed.
3. `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. CI publishes the GitHub Release (and PyPI when enabled). Verify the
   `.deb` installs on a clean Debian/Ubuntu VM or container.
