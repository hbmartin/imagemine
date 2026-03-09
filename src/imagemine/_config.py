"""CLI argument parsing and config resolution."""

import argparse
import os
import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule

from ._db import get_config, set_config

if TYPE_CHECKING:
    import sqlite3


def _resolve_api_key(conn: sqlite3.Connection, key: str, prompt: str) -> str:
    """Resolve an API key: DB config → env var → interactive prompt (then store)."""
    value = get_config(conn, key) or os.environ.get(key)
    if not value:
        value = input(f"{prompt}: ").strip()
        if not value:
            print(f"Error: {key} is required.", file=sys.stderr)
            sys.exit(1)
        set_config(conn, key, value)
        print(f"{key} saved to database.", file=sys.stderr)
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
        help="Image style to use (overrides random selection from styles table)",
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
    return parser.parse_args()
