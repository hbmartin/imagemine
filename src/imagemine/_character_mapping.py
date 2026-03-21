"""Interactive add/remove for character name mappings."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

from ._db import (
    add_character_mapping,
    get_all_character_mappings,
    remove_character_mapping,
)
from ._styles import _parse_style_indices

if TYPE_CHECKING:
    import sqlite3


def _run_add_character_mapping(conn: sqlite3.Connection) -> None:
    """Prompt for an input name and mapped name, then save the mapping."""
    console = Console()
    console.print(Rule("[bold magenta]Add character mapping[/]"))

    input_name = Prompt.ask("[bold]Input name (from Photos)[/]")
    if not input_name.strip():
        console.print("[bold red]Error:[/] Input name is required.")
        sys.exit(1)

    mapped_name = Prompt.ask("[bold]Mapped name (for prompt)[/]")
    if not mapped_name.strip():
        console.print("[bold red]Error:[/] Mapped name is required.")
        sys.exit(1)

    add_character_mapping(conn, input_name.strip(), mapped_name.strip())
    console.print(
        f"\n  [green]\u2713[/] Mapping [cyan]{input_name.strip()}[/]"
        f" \u2192 [magenta]{mapped_name.strip()}[/] saved.",
    )


def _print_numbered_mappings(
    console: Console,
    mappings: list[tuple[str, str]],
) -> None:
    """Print a numbered table of character mappings."""
    table = Table(show_lines=True, border_style="dim")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Input Name", style="cyan")
    table.add_column("Mapped Name", style="magenta")

    for i, (input_name, mapped_name) in enumerate(mappings, 1):
        table.add_row(str(i), input_name, mapped_name)

    console.print(table)


def _run_remove_character_mapping(conn: sqlite3.Connection) -> None:
    """Interactively select and confirm removal of one or more mappings."""
    console = Console()
    console.print(Rule("[bold magenta]Remove character mapping[/]"))

    mappings = get_all_character_mappings(conn)
    if not mappings:
        console.print("[dim]No character mappings found.[/]")
        return

    _print_numbered_mappings(console, mappings)

    raw = Prompt.ask(
        "\n[bold]Enter number(s) to remove[/] [dim](e.g. 1 or 1,3,5)[/]",
        default="",
    )
    if not raw.strip():
        console.print("[dim]Cancelled.[/]")
        return

    unique = _parse_style_indices(raw, len(mappings), console)
    to_remove = [mappings[idx - 1][0] for idx in unique]

    console.print("\nMappings to remove:")
    for name in to_remove:
        console.print(f"  [cyan]{name}[/]")

    confirm = Prompt.ask(
        "\n[bold red]Delete these mappings?[/]",
        choices=["y", "n"],
        default="n",
    )
    if confirm != "y":
        console.print("[dim]Cancelled.[/]")
        return

    for name in to_remove:
        remove_character_mapping(conn, name)

    console.print(
        f"\n  [green]\u2713[/] Removed {len(to_remove)} mapping(s).",
    )
