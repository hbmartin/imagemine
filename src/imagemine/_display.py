"""Rich display helpers for imagemine."""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rich.bar import Bar
from rich.panel import Panel
from rich.table import Table

from ._db import get_all_character_mappings, get_recent_runs
from ._styles import get_all_styles

if TYPE_CHECKING:
    import sqlite3

    from rich.console import Console


def _show_history(conn: sqlite3.Connection, console: Console) -> None:
    """Display recent runs as a Rich table with a relative-time sparkline."""
    runs = get_recent_runs(conn)
    if not runs:
        console.print("[dim]No runs found.[/]")
        return

    def _ms(v: str | None) -> int:
        return int(v) if v is not None else 0

    max_total_ms: float = (
        max(
            (_ms(r[3]) + _ms(r[4]) for r in runs),
            default=1,
        )
        or 1
    )

    table = Table(title="Recent Runs", show_lines=True, border_style="dim")
    table.add_column("Date", style="dim", no_wrap=True)
    table.add_column("Source", style="cyan")
    table.add_column("Style", style="magenta")
    table.add_column("Desc", justify="right", style="yellow")
    table.add_column("Img", justify="right", style="yellow")
    table.add_column("Total", justify="right", style="yellow")
    table.add_column("", no_wrap=True)
    table.add_column("Output", style="green")

    for row in runs:
        started_at, input_path, style, desc_ms, img_ms, output_path = row
        d_ms = _ms(desc_ms)
        i_ms = _ms(img_ms)
        desc_str = f"{d_ms / 1000:.1f}s" if d_ms else "—"
        img_str = f"{i_ms / 1000:.1f}s" if i_ms else "—"
        total_ms: float = d_ms + i_ms
        total_str = f"{total_ms / 1000:.1f}s" if total_ms else "—"
        src = pathlib.Path(input_path).name if input_path else "—"
        out = pathlib.Path(output_path).name if output_path else "—"
        bar = Bar(max_total_ms, 0, total_ms, width=10, color="yellow")
        if started_at:
            try:
                date_str = (
                    datetime.fromisoformat(started_at)
                    .replace(tzinfo=UTC)
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M")
                )
            except ValueError:
                date_str = started_at
        else:
            date_str = "—"
        table.add_row(
            date_str,
            src,
            style or "—",
            desc_str,
            img_str,
            total_str,
            bar,
            out,
        )
    console.print(table)


def _show_styles(conn: sqlite3.Connection, console: Console) -> None:
    """Display all styles as a Rich table."""
    styles = get_all_styles(conn)
    if not styles:
        console.print("[dim]No styles found.[/]")
        return

    table = Table(title="Styles", show_lines=True, border_style="dim")
    table.add_column("Name", style="magenta")
    table.add_column("Description", style="dim")
    table.add_column("Used", justify="right", style="yellow")
    table.add_column("Added", style="dim")

    for name, description, used_count, created_at in styles:
        try:
            local_dt = (
                datetime.fromisoformat(created_at).replace(tzinfo=UTC).astimezone()
            )
            created_at_display = local_dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            created_at_display = created_at or ""
        except TypeError:
            created_at_display = created_at or ""
        table.add_row(name, description, str(used_count), created_at_display)

    console.print(table)
    console.print(f"[dim]Total: {len(styles)} styles[/]")


def _show_character_mappings(conn: sqlite3.Connection, console: Console) -> None:
    """Display all character name mappings as a Rich table."""
    mappings = get_all_character_mappings(conn)
    if not mappings:
        console.print("[dim]No character mappings found.[/]")
        return

    table = Table(title="Character Mappings", show_lines=True, border_style="dim")
    table.add_column("Input Name", style="cyan")
    table.add_column("Mapped Name", style="magenta")

    for input_name, mapped_name in mappings:
        table.add_row(input_name, mapped_name)

    console.print(table)
    console.print(f"[dim]Total: {len(mappings)} mapping(s)[/]")


def _print_summary(  # noqa: PLR0913
    console: Console,
    conn: sqlite3.Connection,
    *,
    run_id: int,
    total_s: float,
    input_path: str,
    input_album: str | None,
    output_path: str,
    destination_album: str | None = None,
) -> None:
    """Print the final summary panel."""
    run_data = conn.execute(
        "SELECT desc_gen_ms, img_gen_ms FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    desc_ms, img_ms = run_data or (None, None)

    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="dim", justify="right")
    grid.add_column()
    grid.add_row("source", f"[cyan]{input_album or input_path}[/]")
    if desc_ms:
        grid.add_row("describe", f"[yellow]{desc_ms / 1000:.1f}s[/]")
    if img_ms:
        grid.add_row("generate", f"[yellow]{img_ms / 1000:.1f}s[/]")
    grid.add_row("total", f"[yellow]{total_s:.1f}s[/]")
    grid.add_row("output", f"[green]{destination_album or output_path}[/]")

    console.rule()
    console.print(Panel(grid, title="[bold green]Done[/]", border_style="green"))
