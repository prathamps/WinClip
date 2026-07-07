#!/usr/bin/env bash
# Remove WinClip from the system (keeps your history database unless --purge).
set -euo pipefail

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }

say "Stopping daemon"
systemctl --user disable --now winclip.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/winclip.service"
systemctl --user daemon-reload

say "Removing package"
if command -v pipx >/dev/null && pipx list 2>/dev/null | grep -q winclip; then
    pipx uninstall winclip
else
    python3 -m pip uninstall -y winclip 2>/dev/null || true
fi

say "Removing desktop entry and keybinding"
rm -f "$HOME/.local/share/applications/io.github.prathamps.WinClip.desktop"
if command -v gsettings >/dev/null; then
    BASE="org.gnome.settings-daemon.plugins.media-keys"
    KEYS_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/winclip/"
    CURRENT=$(gsettings get $BASE custom-keybindings 2>/dev/null || echo "[]")
    if [[ "$CURRENT" == *"$KEYS_PATH"* ]]; then
        NEW=$(python3 - "$CURRENT" "$KEYS_PATH" <<'EOF'
import ast, sys
paths = [p for p in ast.literal_eval(sys.argv[1]) if p != sys.argv[2]]
print(str(paths).replace('"', "'"))
EOF
)
        gsettings set $BASE custom-keybindings "$NEW"
    fi
    gsettings reset org.gnome.shell.keybindings toggle-message-tray 2>/dev/null || true
fi

if [ "${1:-}" = "--purge" ]; then
    say "Purging history and settings"
    rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/winclip" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/winclip"
fi

say "WinClip removed."
