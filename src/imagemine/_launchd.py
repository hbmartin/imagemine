"""launchd plist generation for scheduled imagemine runs."""

from __future__ import annotations

import pathlib
import shutil
import sys
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from rich.console import Console
from rich.prompt import IntPrompt

from ._db import get_config

if TYPE_CHECKING:
    import sqlite3

_REQUIRED_KEYS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "INPUT_ALBUM")

_PLIST_PATH = pathlib.Path("~/Library/LaunchAgents/imagemine.plist").expanduser()

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>imagemine</string>
    <key>ProgramArguments</key>
    <array>
{args}
    </array>
    <key>StartInterval</key>
    <integer>{interval}</integer>
    <key>StandardOutPath</key>
    <string>/tmp/imagemine.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/imagemine.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""


def _check_required_keys(
    conn: sqlite3.Connection,
    config_path: str | None,
    console: Console,
) -> bool:
    """Return True if all required keys are set in the database, else print error."""
    missing = [k for k in _REQUIRED_KEYS if not get_config(conn, k)]
    if not missing:
        return True

    console.print(
        "[bold red]Error:[/] The following keys must be configured"
        " before setting up launchd:",
    )
    for key in missing:
        console.print(f"  [red]✗[/] {key}")
    config_cmd = "imagemine --config"
    if config_path:
        config_cmd += f" --config-path {config_path}"
    console.print(f"\nRun [bold]{config_cmd}[/] to configure them first.")
    return False


def _write_launchd_plist(
    conn: sqlite3.Connection,
    config_path: str | None = None,
    interval_minutes: int | None = None,
) -> None:
    """Write a launchd plist to ~/Library/LaunchAgents/imagemine.plist."""
    console = Console()

    if not _check_required_keys(conn, config_path, console):
        sys.exit(1)

    uvx_bin = shutil.which("uvx")
    if not uvx_bin:
        console.print(
            "[bold red]Error:[/] [bold]uvx[/] is not installed or not on PATH.",
        )
        console.print("\nInstall it via Homebrew:")
        console.print("  [bold]brew install uv[/]")
        console.print("\nOr with the official installer:")
        console.print("  [bold]curl -LsSf https://astral.sh/uv/install.sh | sh[/]")
        sys.exit(1)

    if interval_minutes is None:
        interval_minutes = int(
            IntPrompt.ask("[bold]Run interval (minutes)[/]", console=console),
        )
        if interval_minutes <= 0:
            console.print("[bold red]Error:[/] Interval must be a positive integer.")
            sys.exit(1)

    minutes: int = interval_minutes
    program_args = [uvx_bin, "imagemine"]  # uvx_bin is str after None check above

    if config_path:
        program_args.extend(["--config-path", config_path])

    args_xml = "\n".join(
        f"        <string>{escape(arg)}</string>" for arg in program_args
    )
    plist_content = _PLIST_TEMPLATE.format(
        args=args_xml,
        interval=minutes * 60,
    )

    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PLIST_PATH.write_text(plist_content)

    console.print(f"[green]✓[/] Wrote launchd plist to [cyan]{_PLIST_PATH}[/]")
    console.print("\nTo load and start the scheduled agent, run:")
    console.print(f"  [bold]launchctl load {_PLIST_PATH}[/]")
    console.print("\nTo stop and unload it:")
    console.print(f"  [bold]launchctl unload {_PLIST_PATH}[/]")
