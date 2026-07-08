#!/usr/bin/env bash
# WinClip installer for Debian/Ubuntu-based systems.
#
# Installs system dependencies (apt), the winclip CLI into a dedicated
# virtualenv, a systemd user service, the desktop entry, and — on
# GNOME/COSMIC — binds Super+V to the history panel, just like Windows.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
# Always the distro interpreter, never `python3` from PATH: conda,
# pyenv, and uv shims front a Python that has no PyGObject, and
# installing winclip there breaks it with "No module named 'gi'".
PYTHON=/usr/bin/python3
VENV="$HOME/.local/share/winclip/venv"
say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*"; }

[ -x "$PYTHON" ] || { warn "$PYTHON not found — install the python3 package first"; exit 1; }

# --- 1. system dependencies -------------------------------------------------
say "Checking system dependencies"
APT_PKGS=()
"$PYTHON" -c "import gi" 2>/dev/null || APT_PKGS+=(python3-gi)
"$PYTHON" -c "import gi; gi.require_version('Gtk','3.0')" 2>/dev/null || APT_PKGS+=(gir1.2-gtk-3.0)
"$PYTHON" -c "import ensurepip" 2>/dev/null || APT_PKGS+=(python3-venv)
command -v wl-copy >/dev/null || APT_PKGS+=(wl-clipboard)

# Optional but recommended: paste injection.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    command -v wtype >/dev/null || command -v ydotool >/dev/null || APT_PKGS+=(wtype)
else
    command -v xdotool >/dev/null || APT_PKGS+=(xdotool)
fi

if [ "${#APT_PKGS[@]}" -gt 0 ]; then
    say "Installing packages: ${APT_PKGS[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${APT_PKGS[@]}"
fi

# --- 2. the winclip package -------------------------------------------------
# A dedicated venv on the distro Python sidesteps every pip variant of
# pain: PEP 668 "externally-managed-environment", conda/pyenv shadowing,
# and pipx defaulting to a non-system interpreter.
say "Installing winclip into $VENV"
"$PYTHON" -m venv --clear --system-site-packages "$VENV"
"$VENV/bin/pip" install --quiet "$REPO_DIR"
mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/winclip" "$BIN_DIR/winclip"
"$BIN_DIR/winclip" version >/dev/null || { warn "winclip failed to run after install"; exit 1; }

# Clean up installs made by older versions of this script.
if command -v pipx >/dev/null && pipx list 2>/dev/null | grep -q "^package winclip"; then
    say "Removing old pipx-managed winclip"
    pipx uninstall winclip >/dev/null 2>&1 || true
    ln -sf "$VENV/bin/winclip" "$BIN_DIR/winclip"  # pipx uninstall removes the symlink
fi

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) warn "$BIN_DIR is not on your PATH — add it to your shell profile" ;;
esac

# --- 3. desktop entry & systemd user service --------------------------------
say "Installing desktop entry and systemd user service"
install -Dm644 "$REPO_DIR/data/io.github.prathamps.WinClip.desktop" \
    "$HOME/.local/share/applications/io.github.prathamps.WinClip.desktop"
install -Dm644 "$REPO_DIR/data/winclip.service" \
    "$HOME/.config/systemd/user/winclip.service"
systemctl --user daemon-reload
systemctl --user enable winclip.service
# restart (not just start) so re-running the installer upgrades a
# daemon that is already running
systemctl --user restart winclip.service
say "Daemon status: $(systemctl --user is-active winclip.service)"

# --- 4. Super+V keybinding ---------------------------------------------------
# XDG_CURRENT_DESKTOP is unreliable (Pop!_OS COSMIC sessions may report
# GNOME), so detect the running compositor/shell instead.
bind_cosmic() {
    say "Binding Super+V to the WinClip panel (COSMIC)"
    local FILE="$HOME/.config/cosmic/com.system76.CosmicSettings.Shortcuts/v1/custom"
    mkdir -p "$(dirname "$FILE")"
    [ -f "$FILE" ] || echo "{}" > "$FILE"
    if grep -q 'winclip toggle' "$FILE"; then
        say "WinClip shortcut already present"
        return
    fi
    if grep -Pzoq '(?s)Super,\s*\],\s*key: "v"' "$FILE"; then
        warn "Super+V is already bound in COSMIC — add a shortcut for"
        warn "'$BIN_DIR/winclip toggle' manually in Settings → Keyboard → Shortcuts"
        return
    fi
    python3 - "$FILE" "$BIN_DIR/winclip toggle" <<'EOF'
import sys
path, command = sys.argv[1], sys.argv[2]
text = open(path).read().strip() or "{}"
entry = (
    "    (\n        modifiers: [\n            Super,\n        ],\n"
    '        key: "v",\n'
    f'    ): Spawn("{command}"),\n'
)
body = text.rstrip()[:-1].rstrip()  # drop trailing }
if body != "{" and not body.endswith(","):
    body += ","
open(path, "w").write(body + "\n" + entry + "}\n")
EOF
    say "Super+V is now WinClip (COSMIC reloads shortcuts automatically)"
}

bind_gnome() {
    say "Binding Super+V to the WinClip panel (GNOME)"
    # GNOME uses Super+V for the notification list; free it up first.
    if gsettings list-schemas 2>/dev/null | grep -qx org.gnome.shell.keybindings; then
        gsettings set org.gnome.shell.keybindings toggle-message-tray "[]" || true
    fi
    local KEYS_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/winclip/"
    local BASE="org.gnome.settings-daemon.plugins.media-keys"
    local CURRENT
    CURRENT=$(gsettings get $BASE custom-keybindings)
    if [[ "$CURRENT" != *"$KEYS_PATH"* ]]; then
        if [[ "$CURRENT" == "@as []" || "$CURRENT" == "[]" ]]; then
            NEW="['$KEYS_PATH']"
        else
            NEW="${CURRENT%]*}, '$KEYS_PATH']"
        fi
        gsettings set $BASE custom-keybindings "$NEW"
    fi
    local SCHEMA="$BASE.custom-keybinding:$KEYS_PATH"
    gsettings set "$SCHEMA" name 'WinClip clipboard history'
    gsettings set "$SCHEMA" command "$BIN_DIR/winclip toggle"
    gsettings set "$SCHEMA" binding '<Super>v'
    say "Super+V is now WinClip"
}

if pgrep -x cosmic-comp >/dev/null 2>&1; then
    bind_cosmic
elif pgrep -x gnome-shell >/dev/null 2>&1 && command -v gsettings >/dev/null; then
    bind_gnome
else
    warn "Unknown desktop: bind a shortcut to 'winclip toggle' in your DE settings"
fi

say "Done! Copy something, then press Super+V."
