"""Subcommand dispatch for imagemine CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ._character_mapping import (
    _run_add_character_mapping,
    _run_remove_character_mapping,
)
from ._config import _run_config_wizard
from ._display import _show_character_mappings, _show_history, _show_styles
from ._launchd import _write_launchd_plist
from ._styles import _run_add_style, _run_remove_style

if TYPE_CHECKING:
    import argparse
    import sqlite3
    from collections.abc import Callable

    from rich.console import Console


def dispatch_subcommand(  # noqa: C901, PLR0911
    args: argparse.Namespace,
    conn: sqlite3.Connection,
    console: Console,
    err: Callable[[str], None],
) -> bool:
    """Handle non-pipeline subcommands. Returns True if a subcommand was handled."""
    if args.history:
        _show_history(conn, console)
        return True

    if args.config:
        _run_config_wizard(conn)
        return True

    if args.list_styles:
        _show_styles(conn, console)
        return True

    if args.add_style:
        _run_add_style(conn)
        return True

    if args.remove_style:
        _run_remove_style(conn)
        return True

    if args.list_character_mappings:
        _show_character_mappings(conn, console)
        return True

    if args.add_character_mapping:
        _run_add_character_mapping(conn)
        return True

    if args.remove_character_mapping:
        _run_remove_character_mapping(conn)
        return True

    if args.launchd is not None:
        if args.launchd < 0:
            err("--launchd must be a positive integer.")
            sys.exit(1)
        _write_launchd_plist(
            conn,
            config_path=args.config_path,
            interval_minutes=None if args.launchd == 0 else args.launchd,
        )
        return True

    return False
