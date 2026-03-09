"""CLI argument parsing and config resolution."""

import argparse
import os
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule

from ._db import add_style, get_config, set_config

if TYPE_CHECKING:
    import sqlite3


def _resolve_api_key(conn: sqlite3.Connection, key: str, prompt: str) -> str:
    """Resolve an API key: DB config → env var → interactive prompt (then store)."""
    value = get_config(conn, key) or os.environ.get(key)
    if not value:
        _console = Console()
        value = Prompt.ask(
            f"[bold]{prompt}[/]",
            password=True,
            console=_console,
            default="",
        )
        if not value:
            _console.print(f"[bold red]Error:[/] {key} is required.")
            sys.exit(1)
        set_config(conn, key, value)
        _console.print(f"  [green]✓[/] {key} saved to database.")
    return value


def _resolve_option(  # noqa: PLR0913
    conn: sqlite3.Connection,
    cli_value: str | float | None,
    config_key: str,
    *,
    env_key: str | None = None,
    default: str | float | None = None,
    cast: type = str,
) -> str | float | None:
    """Resolve option via: CLI flag → DB config key → env var → default."""
    if cli_value is not None:
        return cli_value
    stored = get_config(conn, config_key)
    if stored is not None:
        return cast(stored)  # type: ignore[return-value]
    if env_key is not None:
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return cast(env_val)  # type: ignore[return-value]
    return default


_CONFIG_FIELDS: list[tuple[str, str, bool]] = [
    ("ANTHROPIC_API_KEY", "Anthropic API key", True),
    ("GEMINI_API_KEY", "Gemini API key", True),
    ("INPUT_ALBUM", "Input Photos album", False),
    ("DESTINATION_ALBUM", "Destination Photos album", False),
    ("DEFAULT_DESC_TEMP", "Default description temperature", False),
    ("DEFAULT_IMG_TEMP", "Default image temperature", False),
    ("CLAUDE_MODEL", "Claude model override", False),
    ("GEMINI_MODEL", "Gemini model override", False),
]


def _run_config_wizard(conn: sqlite3.Connection) -> None:
    """Interactively walk the user through all configurable keys."""
    console = Console()
    console.print(Rule("[bold magenta]imagemine config[/]"))
    console.print(
        "[dim]Press Enter to keep the existing value. Leave blank to skip.[/]\n",
    )

    for key, label, is_secret in _CONFIG_FIELDS:
        current = get_config(conn, key)

        if is_secret:
            hint = " [dim](stored)[/]" if current else " [dim](not set)[/]"
            console.print(f"[bold]{label}[/]{hint}")
            new_val = Prompt.ask(f"  [cyan]{key}[/]", password=True, default="")
            if new_val:
                set_config(conn, key, new_val)
                console.print(f"  [green]✓ {key} saved[/]")
        else:
            new_val = Prompt.ask(
                f"[bold]{label}[/] [dim]({key})[/]",
                default=current or "",
                show_default=bool(current),
            )
            if new_val:
                set_config(conn, key, new_val)
                console.print("  [green]✓ saved[/]")

    console.print()
    console.print(Rule("[dim]done[/]"))


def _run_add_style(conn: sqlite3.Connection) -> None:
    """Interactively prompt for a new style name and description, then save it."""
    console = Console()
    console.print(Rule("[bold magenta]Add style[/]"))

    name = Prompt.ask("[bold]Style name[/]")
    if not name.strip():
        console.print("[bold red]Error:[/] Name is required.")
        sys.exit(1)

    description = Prompt.ask("[bold]Style description / prompt[/]")
    if not description.strip():
        console.print("[bold red]Error:[/] Description is required.")
        sys.exit(1)

    add_style(conn, name.strip(), description.strip())
    console.print(f"\n  [green]✓[/] Style [magenta]{name.strip()}[/] saved.")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Transform a photo into a fantasy image",
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        default=None,
        help="Path to input image (omit to use --input-album or INPUT_ALBUM config)",
    )
    parser.add_argument(
        "--input-album",
        default=None,
        help="macOS Photos album to pick a random input image from (overrides DB)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory (default: cwd)",
    )
    parser.add_argument(
        "--desc-temp",
        type=float,
        default=None,
        help="Sampling temperature for description generation (overrides DB default)",
    )
    parser.add_argument(
        "--img-temp",
        type=float,
        default=None,
        help="Sampling temperature for image generation (overrides DB default)",
    )
    parser.add_argument(
        "--destination-album",
        default=None,
        help="macOS Photos album to import the generated image into (overrides DB)",
    )
    parser.add_argument(
        "--style",
        default=None,
        metavar="PROMPT",
        help=(
            "Style prompt appended directly to the description."
            " Shows the final prompt and exits without generating an image."
        ),
    )
    parser.add_argument(
        "--list-styles",
        action="store_true",
        help="Show all styles in the database as a table and exit",
    )
    parser.add_argument(
        "--add-style",
        action="store_true",
        help="Interactively add a new style to the database and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached description and regenerate from scratch",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress all output",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show recent runs as a table and exit",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Interactively configure imagemine settings and exit",
    )
    parser.add_argument(
        "--session-svg",
        action="store_true",
        help="Save an SVG of the terminal session alongside the generated image",
    )
    parser.add_argument(
        "--config-path",
        default=None,
        metavar="PATH",
        help="Path to the imagemine database (default: ~/.imagemine.db)",
    )
    return parser.parse_args()
