"""Image processing pipeline for imagemine."""

from __future__ import annotations

import pathlib
import shutil
import sys
import time
from typing import TYPE_CHECKING

from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from rich.tree import Tree

from ._album import _add_to_photos_album, _random_photo_from_album
from ._config import _resolve_api_key, _resolve_option, _resolve_required_option
from ._constants import DEFAULT_DESCRIPTION_MODEL, DEFAULT_IMAGE_MODEL
from ._db import insert_run, update_run
from ._describe import _get_description
from ._display import _print_summary
from ._generate import _run_generation
from ._image import resize_image
from ._styles import increment_style_count, random_style

if TYPE_CHECKING:
    import argparse
    import sqlite3
    from collections.abc import Callable

    from rich.console import Console


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
) -> tuple[str, str | None, pathlib.Path | None]:
    """Return (resolved_input_path, album_photo_id_or_none, temp_export_dir)."""
    if image_path:
        return _validate_input(image_path, err), None, None
    if input_album:
        log(f"Picking random photo from album: {input_album}")
        try:
            path, photo_id, export_dir = _random_photo_from_album(input_album)
        except Exception as e:
            err(f"Failed to fetch photo from album {input_album!r}: {e}")
            sys.exit(1)
        log(f"Selected: {path} (id: {photo_id})")
        return path, photo_id, export_dir
    err("Provide an image path or configure INPUT_ALBUM")
    sys.exit(1)


def run_pipeline(  # noqa: C901, PLR0913, PLR0915
    args: argparse.Namespace,
    conn: sqlite3.Connection,
    console: Console,
    err: Callable[[str], None],
    t_start: float,
    output_dir: pathlib.Path,
) -> None:
    """Run the full resize → describe → style → generate pipeline."""
    desc_temp = _resolve_required_option(
        conn,
        args.desc_temp,
        "DEFAULT_DESC_TEMP",
        default=1.0,
        cast=float,
    )
    img_temp = _resolve_required_option(
        conn,
        args.img_temp,
        "DEFAULT_IMG_TEMP",
        default=1.0,
        cast=float,
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
    claude_model = _resolve_required_option(
        conn,
        None,
        "CLAUDE_MODEL",
        env_key="CLAUDE_MODEL",
        default=DEFAULT_DESCRIPTION_MODEL,
    )
    gemini_model = _resolve_required_option(
        conn,
        None,
        "GEMINI_MODEL",
        env_key="GEMINI_MODEL",
        default=DEFAULT_IMAGE_MODEL,
    )
    anthropic_api_key = _resolve_api_key(
        conn,
        "ANTHROPIC_API_KEY",
        "Enter Anthropic API key",
    )

    console.rule("[bold magenta]imagemine[/]")

    # ── Step 1: Resolve input ──────────────────────────────────────────────
    input_path, input_album_photo_id, input_export_dir = _resolve_input(
        args.image_path,
        str(input_album) if input_album else None,
        log=lambda msg: console.print(f"  [dim]{msg}[/]"),
        err=err,
    )
    run_id = insert_run(conn, input_path)
    if input_album_photo_id:
        update_run(conn, run_id, input_album_photo_id=input_album_photo_id)
    resized_path: pathlib.Path | None = None
    try:
        # ── Step 2: Resize ────────────────────────────────────────────────
        try:
            image, resized_path = resize_image(input_path, output_dir)
        except Exception as e:
            err(f"Failed to open image: {e}")
            sys.exit(1)
        update_run(conn, run_id, resized_file_path=str(resized_path))

        # ── Step 3: Describe ──────────────────────────────────────────────
        console.rule("[dim]Describe[/]", style="dim")

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

            description = _get_description(
                conn,
                run_id,
                image,
                desc_temp,
                anthropic_api_key,
                claude_model,
                getattr(args, "story", None),
                log=log_describe,
                err=err,
            )

        console.print(
            Panel(
                Markdown(description),
                title="[bold cyan]Description[/]",
                border_style="cyan",
                padding=(1, 2),
            ),
        )

        # ── Step 4: Style ─────────────────────────────────────────────────
        console.rule("[dim]Style[/]", style="dim")
        style_name: str | None
        style: str | None
        if args.style:
            style_name = None
            style = args.style
            tree = Tree("[bold]Style (custom)[/]")
            label = Text()
            label.append(f"✦ {style}", style="bold magenta")
            tree.add(label)
            console.print(tree)
            description = f"{description}\n\nStyle: {style}"
            update_run(conn, run_id, style=args.style)
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

        # ── Step 5: Generate ──────────────────────────────────────────────
        console.rule("[dim]Generate[/]", style="dim")
        gemini_api_key = _resolve_api_key(
            conn,
            "GEMINI_API_KEY",
            "Enter Gemini API key",
        )

        with Progress(
            SpinnerColumn(spinner_name="smiley"),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("[bold yellow]Preparing...", total=None)

            def log_generate(msg: str) -> None:
                progress.update(task, description=f"[bold yellow]{msg}")

            output_path = _run_generation(
                conn,
                run_id,
                description,
                image,
                img_temp,
                gemini_api_key,
                output_dir,
                gemini_model,
                log=log_generate,
                err=err,
            )

        # ── Step 6: Add to Photos album (optional) ────────────────────────
        if destination_album:
            try:
                _add_to_photos_album(output_path, str(destination_album), description)
            except Exception as e:
                err(f"Failed to add to Photos album {destination_album!r}: {e}")
                sys.exit(1)
            else:
                console.print(
                    f"  [dim]Added to Photos album:[/] [cyan]{destination_album}[/]",
                )

        # ── Summary ───────────────────────────────────────────────────────
        total_s = time.monotonic() - t_start
        _print_summary(
            console,
            conn,
            run_id,
            total_s,
            input_path,
            style,
            style_name,
            output_path,
        )

        # ── Session SVG (optional) ────────────────────────────────────────
        if args.session_svg:
            svg_path = output_dir / f"imagemine_{run_id}.svg"
            console.save_svg(str(svg_path), title="imagemine")
            console.print(f"  [dim]Session saved:[/] [cyan]{svg_path}[/]")
    finally:
        if resized_path is not None:
            resized_path.unlink(missing_ok=True)
        if input_export_dir is not None:
            shutil.rmtree(input_export_dir, ignore_errors=True)
