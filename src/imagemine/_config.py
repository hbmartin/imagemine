"""CLI argument parsing and config resolution."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, overload

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule

from ._db import get_config, set_config

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable


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


@overload
def _resolve_option(
    conn: sqlite3.Connection,
    cli_value: str | None,
    config_key: str,
    *,
    env_key: str | None = ...,
) -> str | None: ...


@overload
def _resolve_option[T](
    conn: sqlite3.Connection,
    cli_value: T | None,
    config_key: str,
    *,
    env_key: str | None = ...,
    cast: Callable[[str], T],
) -> T | None: ...


def _resolve_option(conn, cli_value, config_key, *, env_key=None, cast=None):
    """Resolve an optional config value via CLI flag → DB → env var."""
    _cast = cast if cast is not None else str
    if cli_value is not None:
        return cli_value
    stored = get_config(conn, config_key)
    if stored is not None:
        return _cast(stored)
    if env_key is not None:
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return _cast(env_val)
    return None


@overload
def _resolve_required_option(
    conn: sqlite3.Connection,
    cli_value: str | None,
    config_key: str,
    *,
    env_key: str | None = ...,
    default: str,
) -> str: ...


@overload
def _resolve_required_option[T](
    conn: sqlite3.Connection,
    cli_value: T | None,
    config_key: str,
    *,
    env_key: str | None = ...,
    default: T,
    cast: Callable[[str], T],
) -> T: ...


def _resolve_required_option(  # noqa: PLR0913
    conn,
    cli_value,
    config_key,
    *,
    env_key=None,
    default,
    cast=None,
):
    """Resolve a required config value via CLI flag → DB → env var → default."""
    if cast is not None:
        resolved = _resolve_option(
            conn,
            cli_value,
            config_key,
            env_key=env_key,
            cast=cast,
        )
    else:
        resolved = _resolve_option(conn, cli_value, config_key, env_key=env_key)
    return default if resolved is None else resolved


_CONFIG_FIELDS: list[tuple[str, str, bool]] = [
    ("ANTHROPIC_API_KEY", "Anthropic API key", True),
    ("GEMINI_API_KEY", "Gemini API key", True),
    ("INPUT_ALBUM", "Input Photos album", False),
    ("DESTINATION_ALBUM", "Destination Photos album", False),
    ("DEFAULT_DESC_TEMP", "Default description temperature", False),
    ("DEFAULT_IMG_TEMP", "Default image temperature", False),
    ("CLAUDE_MODEL", "Claude model override", False),
    ("GEMINI_MODEL", "Gemini model override", False),
    ("DESCRIPTION_PROMPT_SUFFIX", "Description prompt suffix", False),
    ("GENERATION_PROMPT_SUFFIX", "Generation prompt suffix", False),
    ("ASPECT_RATIO", "Image aspect ratio", False),
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
        description="Transform a photo into a re-imagined image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  imagemine photo.jpg                          Basic usage
  imagemine --input-album "Camera Roll"        Random photo from album
  imagemine photo.jpg --style "Watercolor"     Use a specific style
  imagemine photo.jpg --choose-style           Pick style(s) interactively
  imagemine photo.jpg --fresh                  Use a least-used style
  imagemine --list-styles                      Show available styles
  imagemine --add-style                        Add a new style
  imagemine photo.jpg --json                   Output results as JSON
  imagemine photo.jpg --silent                 Print only the output path
  imagemine --config                           Configure settings
  imagemine --history                          Show recent runs
  imagemine --launchd 30                       Schedule runs every 30 min
""",
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
        "--story",
        default=None,
        metavar="TEXT",
        help=(
            "Background context prepended to the Claude prompt"
            " when generating the image description"
        ),
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
        "--fresh",
        action="store_true",
        help=(
            "Pick the style randomly from the least-used styles"
            " (ignored when --style is given)"
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
        "--remove-style",
        action="store_true",
        help="Interactively select and remove styles from the database and exit",
    )
    parser.add_argument(
        "--choose-style",
        action="store_true",
        help="Interactively pick style(s) from the database before running",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress Rich UI; only print the output path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output run results as JSON (suppresses Rich UI)",
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
    parser.add_argument(
        "--aspect-ratio",
        default=None,
        metavar="RATIO",
        help=(
            "Aspect ratio for the generated image (overrides DB / ASPECT_RATIO env)."
            " Must be one of the ratios listed at"
            " https://ai.google.dev/gemini-api/docs/image-generation#aspect_ratios_and_image_size"
            " (e.g. '1:1', '3:4', '4:3', '9:16', '16:9')."
        ),
    )
    parser.add_argument(
        "--launchd",
        nargs="?",
        const=0,
        type=int,
        metavar="MINUTES",
        help=(
            "Write a launchd plist to ~/Library/LaunchAgents/imagemine.plist"
            " that runs imagemine on the given interval (in minutes)."
            " If MINUTES is omitted you will be prompted. Prints the launchctl"
            " command to activate the agent."
        ),
    )
    return parser.parse_args()
