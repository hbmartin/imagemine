"""Command-line interface for imagemine."""

import pathlib
import sys
import threading
import time
from typing import TYPE_CHECKING

from rich.bar import Bar
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ._album import _add_to_photos_album, _random_photo_from_album
from ._config import _parse_args, _resolve_api_key, _resolve_option, _run_config_wizard
from ._core import DB_PATH, resize_image
from ._db import (
    get_recent_runs,
    increment_style_count,
    init_db,
    insert_run,
    random_style,
    update_run,
)
from ._describe import _get_description
from ._generate import _run_generation

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable


def _validate_input(image_path: str, err: Callable[[str], None]) -> str:
    """Validate image_path exists and is a file; return its resolved str path."""
    p = pathlib.Path(image_path)
    if not p.exists():
        err(f"Input file not found: {image_path}")
        sys.exit(1)
    if not p.is_file():
        err(f"Not a file: {image_path}")
        sys.exit(1)
    return str(p.resolve())


def _resolve_input(
    image_path: str | None,
    input_album: str | None,
    *,
    log: Callable[[str], None],
    err: Callable[[str], None],
) -> tuple[str, str | None]:
    """Return (resolved_input_path, album_photo_id_or_none)."""
    if image_path:
        return _validate_input(image_path, err), None
    if input_album:
        log(f"Picking random photo from album: {input_album}")
        try:
            path, photo_id = _random_photo_from_album(input_album)
        except Exception as e:  # noqa: BLE001
            err(f"Failed to fetch photo from album {input_album!r}: {e}")
            sys.exit(1)
        log(f"Selected: {path} (id: {photo_id})")
        return path, photo_id
    err("Provide an image path or configure INPUT_ALBUM")
    sys.exit(1)


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
        table.add_row(
            started_at or "—",
            src,
            style or "—",
            desc_str,
            img_str,
            total_str,
            bar,
            out,
        )
    console.print(table)


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    """Run the imagemine pipeline: resize, describe, generate."""
    args = _parse_args()
    t_start = time.monotonic()
    console = Console(quiet=args.silent, record=args.session_svg)

    def err(msg: str) -> None:
        console.print(f"[bold red]Error:[/] {msg}")
        if sys.exc_info()[0] is not None:
            console.print_exception(show_locals=False)

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = init_db(DB_PATH)

    if args.history:
        _show_history(conn, console)
        return

    if args.config:
        _run_config_wizard(conn)
        return

    desc_temp = float(
        _resolve_option(
            conn,
            args.desc_temp,
            "DEFAULT_DESC_TEMP",
            default=1.0,
            cast=float,
        )
        or 1.0,
    )
    img_temp = float(
        _resolve_option(
            conn,
            args.img_temp,
            "DEFAULT_IMG_TEMP",
            default=1.0,
            cast=float,
        )
        or 1.0,
    )
    input_album = _resolve_option(
        conn,
        args.input_album,
        "INPUT_ALBUM",
        env_key="INPUT_ALBUM",
    )
    destination_album = _resolve_option(
        conn,
        args.destination_album,
        "DESTINATION_ALBUM",
        env_key="DESTINATION_ALBUM",
    )
    anthropic_api_key = _resolve_api_key(
        conn,
        "ANTHROPIC_API_KEY",
        "Enter Anthropic API key",
    )
    gemini_api_key = _resolve_api_key(conn, "GEMINI_API_KEY", "Enter Gemini API key")

    console.rule("[bold magenta]imagemine[/]")

    # ── Step 1: Resolve input ──────────────────────────────────────────────
    input_path, input_album_photo_id = _resolve_input(
        args.image_path,
        str(input_album) if input_album else None,
        log=lambda msg: console.print(f"  [dim]{msg}[/]"),
        err=err,
    )
    run_id = insert_run(conn, input_path)
    if input_album_photo_id:
        update_run(conn, run_id, input_album_photo_id=input_album_photo_id)

    # ── Step 2: Resize ────────────────────────────────────────────────────
    console.rule("[dim]Resize[/]", style="dim")
    with console.status("[dim]Resizing image...[/]", spinner="line"):
        try:
            image, resized_path = resize_image(input_path, output_dir)
        except Exception as e:  # noqa: BLE001
            err(f"Failed to open image: {e}")
            sys.exit(1)
    update_run(conn, run_id, resized_file_path=str(resized_path))
    console.print(f"  [dim]→[/] [cyan]{resized_path.name}[/]")

    # ── Step 3: Describe ──────────────────────────────────────────────────
    console.rule("[dim]Describe[/]", style="dim")
    _desc_result: list[str | None] = [None]
    _desc_exit: list[int | None] = [None]

    with Progress(
        SpinnerColumn(spinner_name="moon"),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[bold cyan]Preparing...", total=None)

        def log_describe(msg: str) -> None:
            progress.update(task, description=f"[bold cyan]{msg}")

        def _describe_worker() -> None:
            try:
                _desc_result[0] = _get_description(
                    conn,
                    run_id,
                    image,
                    input_path,
                    desc_temp,
                    anthropic_api_key,
                    force=args.force,
                    log=log_describe,
                    err=err,
                )
            except SystemExit as exc:
                _desc_exit[0] = int(exc.code) if exc.code is not None else 1

        t = threading.Thread(target=_describe_worker, daemon=True)
        t.start()
        t.join()

    if _desc_exit[0] is not None:
        sys.exit(_desc_exit[0])
    if _desc_result[0] is None:
        err("Description generation returned no result.")
        sys.exit(1)
    description = _desc_result[0]

    console.print(
        Panel(
            Markdown(description),
            title="[bold cyan]Description[/]",
            border_style="cyan",
            padding=(1, 2),
        ),
    )

    # ── Step 4: Style ─────────────────────────────────────────────────────
    console.rule("[dim]Style[/]", style="dim")
    style_name: str | None
    if args.style:
        style_name = args.style
        style_desc = ""
        style: str | None = args.style
    else:
        style_name, style_desc = random_style(conn)
        style = f"{style_name}: {style_desc}" if style_name else None

    if style and style_name:
        tree = Tree("[bold]Selected style[/]")
        label = Text()
        label.append(f"✦ {style_name}", style="bold magenta")
        if style_desc:
            label.append(f"  —  {style_desc}", style="dim")
        tree.add(label)
        console.print(tree)
        description = f"{description}\n\nStyle: {style}"
        update_run(conn, run_id, style=style)
        increment_style_count(conn, style_name)

    # ── Step 5: Generate ──────────────────────────────────────────────────
    console.rule("[dim]Generate[/]", style="dim")
    _gen_result: list[str | None] = [None]
    _gen_exit: list[int | None] = [None]

    with Progress(
        SpinnerColumn(spinner_name="arc"),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("[bold yellow]Preparing...", total=None)

        def log_generate(msg: str) -> None:
            progress.update(task, description=f"[bold yellow]{msg}")

        def _generate_worker() -> None:
            try:
                _gen_result[0] = _run_generation(
                    conn,
                    run_id,
                    description,
                    image,
                    img_temp,
                    gemini_api_key,
                    output_dir,
                    log=log_generate,
                    err=err,
                )
            except SystemExit as exc:
                _gen_exit[0] = int(exc.code) if exc.code is not None else 1

        t = threading.Thread(target=_generate_worker, daemon=True)
        t.start()
        t.join()

    if _gen_exit[0] is not None:
        sys.exit(_gen_exit[0])
    if _gen_result[0] is None:
        err("Image generation returned no result.")
        sys.exit(1)
    output_path = _gen_result[0]

    resized_path.unlink(missing_ok=True)

    # ── Step 6: Add to Photos album (optional) ────────────────────────────
    if destination_album:
        try:
            _add_to_photos_album(output_path, str(destination_album))
        except Exception as e:  # noqa: BLE001
            err(f"Failed to add to Photos album {destination_album!r}: {e}")
        else:
            console.print(
                f"  [dim]Added to Photos album:[/] [cyan]{destination_album}[/]",
            )

    # ── Summary ───────────────────────────────────────────────────────────
    run_data = conn.execute(
        "SELECT desc_gen_ms, img_gen_ms FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    desc_ms, img_ms = run_data or (None, None)
    total_s = time.monotonic() - t_start

    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="dim", justify="right")
    grid.add_column()
    grid.add_row("source", f"[cyan]{pathlib.Path(input_path).name}[/]")
    if style and style_name:
        grid.add_row("style", f"[magenta]{style_name}[/]")
    if desc_ms:
        grid.add_row("describe", f"[yellow]{desc_ms / 1000:.1f}s[/]")
    if img_ms:
        grid.add_row("generate", f"[yellow]{img_ms / 1000:.1f}s[/]")
    grid.add_row("total", f"[yellow]{total_s:.1f}s[/]")
    grid.add_row("output", f"[green]{output_path}[/]")

    console.rule()
    console.print(Panel(grid, title="[bold green]Done[/]", border_style="green"))

    # ── Session SVG (optional) ────────────────────────────────────────────
    if args.session_svg:
        svg_path = output_dir / f"imagemine_{run_id}.svg"
        console.save_svg(str(svg_path), title="imagemine")
        console.print(f"  [dim]Session saved:[/] [cyan]{svg_path}[/]")
