"""Command-line driving adapter.

``winclip``          start the daemon (clipboard capture + hidden panel)
``winclip toggle``   show/hide the panel of the running daemon
                     (starts the daemon with the panel open if needed)
``winclip show``     show the panel
``winclip list``     print the history to stdout
``winclip clear``    clear unpinned history
``winclip config``   get or set a setting
``winclip version``  print the version
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys

from winclip import __version__
from winclip.domain import Settings


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="winclip",
        description="A Windows-style clipboard history (Win+V) for Linux.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.set_defaults(func=_cmd_daemon)
    sub = parser.add_subparsers(title="commands")

    sub.add_parser("daemon", help="run the clipboard daemon").set_defaults(
        func=_cmd_daemon
    )
    sub.add_parser("toggle", help="show/hide the history panel").set_defaults(
        func=lambda a: _cmd_panel(a, "toggle")
    )
    sub.add_parser("show", help="show the history panel").set_defaults(
        func=lambda a: _cmd_panel(a, "show")
    )
    sub.add_parser("quit", help="stop the running daemon").set_defaults(
        func=_cmd_quit
    )

    p_list = sub.add_parser("list", help="print history to stdout")
    p_list.add_argument("-n", "--limit", type=int, default=20)
    p_list.set_defaults(func=_cmd_list)

    sub.add_parser("clear", help="clear unpinned history").set_defaults(
        func=_cmd_clear
    )

    p_paste = sub.add_parser(
        "paste", help="copy a history item to the clipboard by id prefix"
    )
    p_paste.add_argument("id", help="item id (prefix is enough, see 'winclip list')")
    p_paste.set_defaults(func=_cmd_paste)

    p_cfg = sub.add_parser("config", help="get or set a setting")
    p_cfg.add_argument("key", nargs="?", help="setting name")
    p_cfg.add_argument("value", nargs="?", help="new value")
    p_cfg.set_defaults(func=_cmd_config)

    sub.add_parser("version", help="print version").set_defaults(func=_cmd_version)
    return parser


# -- daemon / panel ----------------------------------------------------


def _cmd_daemon(_args) -> int:
    return _run_app(show_on_start=False)


def _cmd_panel(_args, action: str) -> int:
    from winclip.adapters.driving.gtk.app import send_action_to_running_instance

    if send_action_to_running_instance(action):
        return 0
    # No daemon yet: become one, with the panel open.
    return _run_app(show_on_start=True)


def _cmd_quit(_args) -> int:
    from winclip.adapters.driving.gtk.app import send_action_to_running_instance

    if not send_action_to_running_instance("quit"):
        print("winclip daemon is not running", file=sys.stderr)
        return 1
    return 0


def _run_app(show_on_start: bool) -> int:
    from winclip.adapters.driving.gtk.app import WinClipApplication
    from winclip.bootstrap import build_core

    container = build_core(with_monitor=True)
    app = WinClipApplication(container, show_on_start=show_on_start)
    return app.run(None)


# -- headless commands -------------------------------------------------


def _cmd_list(args) -> int:
    from winclip.bootstrap import build_core

    container = build_core(with_monitor=False)
    try:
        items = container.query.list_items()[: args.limit]
        if not items:
            print("(history is empty)")
            return 0
        for item in items:
            pin = "*" if item.pinned else " "
            print(f"{pin} {item.id[:8]}  {item.preview(100)}")
    finally:
        container.shutdown()
    return 0


def _cmd_clear(_args) -> int:
    from winclip.bootstrap import build_core

    container = build_core(with_monitor=False)
    try:
        removed = container.manage.clear()
        print(f"removed {removed} item(s)")
    finally:
        container.shutdown()
    return 0


def _cmd_paste(args) -> int:
    from winclip.bootstrap import build_core

    container = build_core(with_monitor=False)
    try:
        matches = [
            i for i in container.query.list_items() if i.id.startswith(args.id)
        ]
        if not matches:
            print(f"no item with id {args.id}", file=sys.stderr)
            return 1
        if len(matches) > 1:
            print(f"ambiguous id prefix {args.id}", file=sys.stderr)
            return 1
        result = container.activate.activate(matches[0].id)
        print("pasted" if result.pasted else "copied to clipboard")
    finally:
        container.shutdown()
    return 0


def _cmd_config(args) -> int:
    from winclip.bootstrap import build_core

    container = build_core(with_monitor=False)
    try:
        current = container.settings.get_settings()
        if args.key is None:
            for key, value in dataclasses.asdict(current).items():
                print(f"{key} = {value}")
            return 0
        if args.key not in {f.name for f in dataclasses.fields(Settings)}:
            print(f"unknown setting: {args.key}", file=sys.stderr)
            return 1
        if args.value is None:
            print(getattr(current, args.key))
            return 0
        try:
            updated = dataclasses.replace(
                current, **{args.key: _coerce(current, args.key, args.value)}
            )
        except ValueError as exc:
            print(f"invalid value: {exc}", file=sys.stderr)
            return 1
        container.settings.update_settings(updated)
        print(f"{args.key} = {getattr(updated, args.key)}")
    finally:
        container.shutdown()
    return 0


def _coerce(current: Settings, key: str, raw: str):
    existing = getattr(current, key)
    if isinstance(existing, bool):
        if raw.lower() in ("true", "1", "yes", "on"):
            return True
        if raw.lower() in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"expected a boolean, got {raw!r}")
    if isinstance(existing, int):
        return int(raw)
    return raw


def _cmd_version(_args) -> int:
    print(f"winclip {__version__}")
    return 0
