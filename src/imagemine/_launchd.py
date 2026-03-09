"""launchd plist generation for scheduled imagemine runs."""

import pathlib
import shutil
import sys

from rich.console import Console
from rich.prompt import IntPrompt

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


def _write_launchd_plist(
    config_path: str | None = None,
    interval_minutes: int | None = None,
) -> None:
    """Write a launchd plist to ~/Library/LaunchAgents/imagemine.plist."""
    console = Console()

    if interval_minutes is None:
        interval_minutes = IntPrompt.ask(
            "[bold]Run interval (minutes)[/]",
            console=console,
        )
        if interval_minutes <= 0:
            console.print("[bold red]Error:[/] Interval must be a positive integer.")
            sys.exit(1)

    imagemine_bin = shutil.which("imagemine")
    if imagemine_bin:
        program_args = [imagemine_bin]
    else:
        uvx_bin = shutil.which("uvx") or "uvx"
        program_args = [uvx_bin, "imagemine"]

    if config_path:
        program_args.extend(["--config-path", config_path])

    args_xml = "\n".join(f"        <string>{arg}</string>" for arg in program_args)
    plist_content = _PLIST_TEMPLATE.format(
        args=args_xml,
        interval=interval_minutes * 60,
    )

    _PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PLIST_PATH.write_text(plist_content)

    console.print(f"[green]✓[/] Wrote launchd plist to [cyan]{_PLIST_PATH}[/]")
    console.print("\nTo load and start the scheduled agent, run:")
    console.print(f"  [bold]launchctl load {_PLIST_PATH}[/]")
    console.print("\nTo stop and unload it:")
    console.print(f"  [bold]launchctl unload {_PLIST_PATH}[/]")
