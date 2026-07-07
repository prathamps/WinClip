"""PasteInjector implementation: synthesise Ctrl+V with external tools.

Key injection on Linux depends on the display server and installed
tooling. We probe, in order of preference for the current session:

* Wayland: ``ydotool`` (uinput, works everywhere but needs its daemon),
  then ``wtype`` (works on wlroots compositors).
* X11: ``xdotool``.

When nothing is available :meth:`paste` returns False and the caller
falls back to copy-only, which the UI communicates to the user.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

log = logging.getLogger(__name__)

# key 29 = LEFTCTRL, key 47 = V (Linux input event codes, used by ydotool)
_CANDIDATES: dict[str, list[str]] = {
    "ydotool": ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
    "wtype": ["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
    "xdotool": ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
}
_WAYLAND_ORDER = ["ydotool", "wtype"]
_X11_ORDER = ["xdotool", "ydotool"]


class CommandPasteInjector:
    def __init__(
        self,
        session_type: str,
        preferred_tool: str = "auto",
        focus_delay_s: float = 0.15,
    ) -> None:
        self._session_type = session_type
        self._preferred = preferred_tool
        self._focus_delay_s = focus_delay_s

    def paste(self) -> bool:
        cmd = self._resolve_command()
        if cmd is None:
            log.debug("no paste-injection tool available")
            return False
        # Give the compositor a moment to return focus to the target
        # window after our panel hides.
        time.sleep(self._focus_delay_s)
        try:
            subprocess.run(cmd, check=True, timeout=5, capture_output=True)
            return True
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            log.warning("paste injection with %s failed: %s", cmd[0], exc)
            return False

    def _resolve_command(self) -> list[str] | None:
        if self._preferred == "none":
            return None
        if self._preferred != "auto":
            cmd = _CANDIDATES.get(self._preferred)
            return cmd if cmd and shutil.which(cmd[0]) else None
        order = _WAYLAND_ORDER if self._session_type == "wayland" else _X11_ORDER
        for name in order:
            if shutil.which(name):
                return _CANDIDATES[name]
        return None
