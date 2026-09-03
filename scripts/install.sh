#!/usr/bin/env bash
# WinClip installer for Debian/Ubuntu (apt) and Arch/Omarchy (pacman).
#
# Installs system dependencies, the winclip CLI into a dedicated
# virtualenv, a systemd user service, the desktop entry, and — on
# GNOME, COSMIC, and Hyprland — binds Super+V to the history panel,
# just like Windows.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
# Always the distro interpreter, never `python3` from PATH: conda,
# pyenv, and uv shims front a Python that has no PyGObject, and
# installing winclip there breaks it with "No module named 'gi'".
PYTHON=/usr/bin/python3
VENV="$HOME/.local/share/winclip/venv"
APP_ID="io.github.prathamps.WinClip"
say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*"; }

[ -x "$PYTHON" ] || { warn "$PYTHON not found — install the python3 package first"; exit 1; }

# WinClip needs Python 3.10+. Fail here with a clear message: old pips
# (Ubuntu 20.04's pip 20) only *warn* about a Requires-Python mismatch
# and then produce a broken install.
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    warn "WinClip needs Python 3.10 or newer; $PYTHON is $("$PYTHON" -V 2>&1 | cut -d' ' -f2)."
    warn "Supported distributions: Debian 12+, Ubuntu 22.04+, Pop!_OS 22.04+, Arch Linux, Omarchy."
    exit 1
fi

# --- 1. system dependencies -------------------------------------------------
if command -v apt-get >/dev/null; then
    PKG_MANAGER=apt
    PKG_GI=python3-gi PKG_GTK=gir1.2-gtk-3.0 PKG_VENV=python3-venv
    PKG_LAYER_SHELL=gir1.2-gtklayershell-0.1
elif command -v pacman >/dev/null; then
    PKG_MANAGER=pacman
    PKG_GI=python-gobject PKG_GTK=gtk3 PKG_VENV=""
    PKG_LAYER_SHELL=gtk-layer-shell
else
    PKG_MANAGER=none
    PKG_GI=PyGObject PKG_GTK="GTK 3 introspection data" PKG_VENV="python venv"
    PKG_LAYER_SHELL=gtk-layer-shell
fi

install_packages() {
    case "$PKG_MANAGER" in
        apt)    sudo apt-get update -qq && sudo apt-get install -y "$@" ;;
        pacman) sudo pacman -S --needed --noconfirm "$@" ;;
        *)      warn "No supported package manager found; install these yourself: $*"; exit 1 ;;
    esac
}

say "Checking system dependencies"
PKGS=()
"$PYTHON" -c "import gi" 2>/dev/null || PKGS+=("$PKG_GI")
"$PYTHON" -c "import gi; gi.require_version('Gtk','3.0')" 2>/dev/null || PKGS+=("$PKG_GTK")
"$PYTHON" -c "import ensurepip" 2>/dev/null || PKGS+=(${PKG_VENV:+"$PKG_VENV"})
command -v wl-copy >/dev/null || PKGS+=(wl-clipboard)

if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    "$PYTHON" -c "import gi; gi.require_version('GtkLayerShell','0.1')" 2>/dev/null \
        || PKGS+=("$PKG_LAYER_SHELL")
    # Optional but recommended: paste injection.
    command -v wtype >/dev/null || command -v ydotool >/dev/null || PKGS+=(wtype)
else
    command -v xdotool >/dev/null || PKGS+=(xdotool)
fi

if [ "${#PKGS[@]}" -gt 0 ]; then
    say "Installing packages: ${PKGS[*]}"
    install_packages "${PKGS[@]}"
fi

# --- 2. the winclip package -------------------------------------------------
# A dedicated venv on the distro Python sidesteps every pip variant of
# pain: PEP 668 "externally-managed-environment", conda/pyenv shadowing,
# and pipx defaulting to a non-system interpreter.
say "Installing winclip into $VENV"
"$PYTHON" -m venv --clear --system-site-packages "$VENV"
# Not --quiet: pip's output is the only diagnostic when a build fails.
"$VENV/bin/pip" install "$REPO_DIR"
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
install -Dm644 "$REPO_DIR/data/$APP_ID.desktop" \
    "$HOME/.local/share/applications/$APP_ID.desktop"
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

bind_hyprland() {
    local HYPR_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hypr"
    local COMMAND="$BIN_DIR/winclip toggle"
    if [ -f "$HYPR_DIR/hyprland.lua" ]; then
        say "Binding Super+V to the WinClip panel (Hyprland, Lua config)"
        cat > "$HYPR_DIR/winclip.lua" <<EOF
-- WinClip: Super+V opens the clipboard history, like Windows.
-- Written by WinClip's install.sh; remove with scripts/uninstall.sh.
pcall(hl.unbind, "SUPER + V")
hl.bind("SUPER + V", hl.dsp.exec_cmd("$COMMAND"), { description = "Clipboard history" })
hl.window_rule({ match = { class = "^($APP_ID)\$" }, float = true, center = true })
EOF
        local LINE="dofile(\"$HYPR_DIR/winclip.lua\") -- winclip"
        grep -qF "$HYPR_DIR/winclip.lua" "$HYPR_DIR/hyprland.lua" \
            || printf '\n%s\n' "$LINE" >> "$HYPR_DIR/hyprland.lua"
    elif [ -f "$HYPR_DIR/hyprland.conf" ]; then
        say "Binding Super+V to the WinClip panel (Hyprland, hyprland.conf)"
        cat > "$HYPR_DIR/winclip.conf" <<EOF
# WinClip: Super+V opens the clipboard history, like Windows.
# Written by WinClip's install.sh; remove with scripts/uninstall.sh.
unbind = SUPER, V
bind = SUPER, V, exec, $COMMAND
windowrule = float, class:^($APP_ID)\$
windowrule = center, class:^($APP_ID)\$
EOF
        grep -qF "winclip.conf" "$HYPR_DIR/hyprland.conf" \
            || printf '\nsource = %s\n' "$HYPR_DIR/winclip.conf" >> "$HYPR_DIR/hyprland.conf"
    else
        warn "No Hyprland config found in $HYPR_DIR — bind Super+V to '$COMMAND' yourself"
        return
    fi
    if command -v hyprctl >/dev/null; then
        hyprctl reload >/dev/null || warn "hyprctl reload failed — check 'hyprctl configerrors'"
    fi
    say "Super+V is now WinClip (replacing Hyprland's float toggle / Omarchy's universal paste)"
}

if pgrep -x cosmic-comp >/dev/null 2>&1; then
    bind_cosmic
elif [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] || pgrep -x Hyprland >/dev/null 2>&1; then
    bind_hyprland
elif pgrep -x gnome-shell >/dev/null 2>&1 && command -v gsettings >/dev/null; then
    bind_gnome
else
    warn "Unknown desktop: bind a shortcut to 'winclip toggle' in your DE settings"
fi

say "Done! Copy something, then press Super+V."
