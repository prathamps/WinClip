#!/usr/bin/env bash
# Build a Debian package for WinClip using plain dpkg-deb.
#
# The result installs system-wide: the package under
# /usr/lib/python3/dist-packages, a /usr/bin/winclip launcher, the
# desktop entry, and a systemd *user* unit. Each user opts in with:
#   systemctl --user enable --now winclip.service
#
# Usage: scripts/build-deb.sh [output-dir]   (default: ./dist)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$REPO_DIR/dist}"
VERSION=$(python3 - <<EOF
import re
print(re.search(r'^version = "([^"]+)"', open("$REPO_DIR/pyproject.toml").read(), re.M).group(1))
EOF
)

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/winclip_${VERSION}_all"

# --- payload -----------------------------------------------------------------
install -d "$PKG/usr/lib/python3/dist-packages"
cp -r "$REPO_DIR/src/winclip" "$PKG/usr/lib/python3/dist-packages/"
find "$PKG" -name __pycache__ -type d -exec rm -rf {} +

install -d "$PKG/usr/bin"
cat > "$PKG/usr/bin/winclip" <<'EOF'
#!/usr/bin/python3
import sys

from winclip.adapters.driving.cli import main

if __name__ == "__main__":
    sys.exit(main())
EOF
chmod 755 "$PKG/usr/bin/winclip"

install -Dm644 "$REPO_DIR/data/io.github.prathamps.WinClip.desktop" \
    "$PKG/usr/share/applications/io.github.prathamps.WinClip.desktop"

# The repo's unit points at ~/.local/bin for source installs; the
# system package uses /usr/bin.
install -d "$PKG/usr/lib/systemd/user"
sed 's|%h/.local/bin/winclip|/usr/bin/winclip|' \
    "$REPO_DIR/data/winclip.service" > "$PKG/usr/lib/systemd/user/winclip.service"

install -Dm644 "$REPO_DIR/LICENSE" "$PKG/usr/share/doc/winclip/copyright"

# --- control -----------------------------------------------------------------
install -d "$PKG/DEBIAN"
cat > "$PKG/DEBIAN/control" <<EOF
Package: winclip
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, wl-clipboard
Recommends: wtype, xdotool
Suggests: ydotool
Maintainer: Pratham P S <pratham@incubyte.co>
Homepage: https://github.com/prathamps/WinClip
Description: Windows-style clipboard history (Win+V) for Linux
 WinClip recreates the Windows 11 clipboard experience on Linux
 desktops: a Super+V panel with searchable clipboard history (text and
 images), pinning, emoji/kaomoji/symbol pickers, and a shell-command
 history browser. Works on Wayland and X11.
 .
 After installing, each user enables the daemon with:
   systemctl --user enable --now winclip.service
 and binds Super+V to "winclip toggle" in their desktop settings.
EOF

mkdir -p "$OUT_DIR"
dpkg-deb --build --root-owner-group "$PKG" "$OUT_DIR" >/dev/null
echo "built: $OUT_DIR/winclip_${VERSION}_all.deb"
