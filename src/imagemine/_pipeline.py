"""Image processing pipeline for imagemine."""

from __future__ import annotations

import pathlib
import shutil
import sys
import time
from typing import TYPE_CHECKING, NamedTuple

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from ._db import insert_run, update_run
from ._describe import _get_description
from ._display import _print_summary
from ._generate import _run_generation
from ._image import resize_image
from ._styles import increment_style_count, least_used_style, random_style

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

    from PIL import Image
    from rich.console import Console

    from ._photos import PhotosBackend
    from ._progress import ProgressReporter


class PipelineResult(NamedTuple):
    """Result of a pipeline run."""

    output_path: str
    run_id: int


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
    photos: PhotosBackend | None,
    log: Callable[[str], None],
    err: Callable[[str], None],
) -> tuple[str, str | None, pathlib.Path | None, list[str]]:
    """Return (resolved_input_path, photo_id, temp_dir, people_names)."""
    if image_path:
        return _validate_input(image_path, err), None, None, []
    if input_album:
        if photos is None:
            err("No photos backend available for album support")
            sys.exit(1)
        log(f"Picking random photo from album: {input_album}")
        try:
            path, photo_id, export_dir, people_names = photos.random_photo_from_album(
                input_album,
            )
        except Exception as e:
            err(f"Failed to fetch photo from album {input_album!r}: {e}")
            sys.exit(1)
        log(f"Selected: {path} (id: {photo_id})")
        if people_names:
            log(f"Characters: {', '.join(people_names)}")
        return path, photo_id, export_dir, people_names
    err("Provide an image path or configure INPUT_ALBUM")
    sys.exit(1)


def _step_resize(
    conn: sqlite3.Connection,
    run_id: int,
    input_path: str,
    output_dir: pathlib.Path,
    err: Callable[[str], None],
) -> tuple[Image.Image, pathlib.Path]:
    """Resize the input image and record the path in the database."""
    try:
        image, resized_path = resize_image(input_path, output_dir)
    except Exception as e:
        err(f"Failed to open image: {e}")
        sys.exit(1)
    update_run(conn, run_id, resized_file_path=str(resized_path))
    return image, resized_path


def _step_describe(  # noqa: PLR0913
    conn: sqlite3.Connection,
    console: Console,
    run_id: int,
    image: Image.Image,
    *,
    desc_temp: float,
    anthropic_api_key: str,
    claude_model: str,
    story: str | None,
    desc_prompt_suffix: str | None,
    people_names: list[str],
    progress: ProgressReporter,
    err: Callable[[str], None],
) -> str:
    """Generate and display a description via Claude."""
    console.rule("[dim]Describe[/]", style="dim")

    with progress.step("moon", "cyan") as log_describe:
        description = _get_description(
            conn,
            run_id,
            image,
            desc_temp=desc_temp,
            api_key=anthropic_api_key,
            model=claude_model,
            story=story,
            prompt_suffix=desc_prompt_suffix,
            people_names=people_names,
            log=log_describe,
            err=err,
        )

    console.print(
        Panel(
            Markdown(description),
            title=None,
            border_style="cyan",
            padding=(1, 2),
        ),
    )
    return description


def _step_style(  # noqa: PLR0913
    conn: sqlite3.Connection,
    console: Console,
    run_id: int,
    description: str,
    *,
    style: str | None,
    selected_style_names: tuple[str, ...],
    fresh: bool,
    gen_prompt_suffix: str | None,
) -> str:
    """Apply a style to the description and return the updated prompt."""
    console.rule("[dim]Style[/]", style="dim")

    if style and selected_style_names:
        content = Text()
        content.append(f"Style: {style}", style="bold magenta")
        console.print(Panel(content, title=None, border_style="magenta"))
        description = f"{description}\n\nStyle: {style}"
        update_run(conn, run_id, style=style)
        for style_name in selected_style_names:
            increment_style_count(conn, style_name)
    elif style:
        content = Text()
        content.append(f"✦ {style}", style="bold magenta")
        console.print(
            Panel(content, title="[bold]Style (custom)[/]", border_style="magenta"),
        )
        description = f"{description}\n\nStyle: {style}"
        update_run(conn, run_id, style=style)
    else:
        style_name, style_desc = least_used_style(conn) if fresh else random_style(conn)
        resolved = f"{style_name}: {style_desc}" if style_name else None

        if resolved and style_name:
            content = Text()
            content.append(f"✦ {style_name}", style="bold magenta")
            if style_desc:
                content.append(f"  —  {style_desc}", style="dim")
            console.print(
                Panel(content, title=None, border_style="magenta"),
            )
            description = f"{description}\n\nStyle: {resolved}"
            update_run(conn, run_id, style=resolved)
            increment_style_count(conn, style_name)

    if gen_prompt_suffix:
        description = f"{description}\n\n{gen_prompt_suffix}"

    return description


def _step_generate(  # noqa: PLR0913
    conn: sqlite3.Connection,
    console: Console,
    run_id: int,
    description: str,
    image: Image.Image,
    *,
    img_temp: float,
    gemini_api_key: str,
    output_dir: pathlib.Path,
    gemini_model: str,
    aspect_ratio: str | None,
    progress: ProgressReporter,
    err: Callable[[str], None],
) -> str:
    """Generate the image via Gemini and return the output path."""
    console.rule("[dim]Generate[/]", style="dim")

    with progress.step("smiley", "yellow") as log_generate:
        output_path = _run_generation(
            conn,
            run_id,
            description,
            image,
            img_temp=img_temp,
            api_key=gemini_api_key,
            output_dir=output_dir,
            model=gemini_model,
            aspect_ratio=aspect_ratio or "4:3",
            log=log_generate,
            err=err,
        )

    console.print(f"  [dim]Output:[/] [green]{output_path}[/]")
    return output_path


def _step_album_import(
    output_path: str,
    description: str,
    *,
    destination_album: str | None,
    photos: PhotosBackend | None,
    err: Callable[[str], None],
) -> str | None:
    """Optionally import the generated image into a Photos album."""
    if not destination_album or photos is None:
        return None
    try:
        photos.add_to_photos_album(output_path, destination_album, description)
    except Exception as e:
        err(f"Failed to add to Photos album {destination_album!r}: {e}")
        return None
    return destination_album


def run_pipeline(  # noqa: PLR0913
    conn: sqlite3.Connection,
    console: Console,
    err: Callable[[str], None],
    t_start: float,
    output_dir: pathlib.Path,
    *,
    image_path: str | None,
    input_album: str | None,
    destination_album: str | None,
    desc_temp: float,
    img_temp: float,
    claude_model: str,
    gemini_model: str,
    anthropic_api_key: str,
    gemini_api_key: str,
    story: str | None,
    style: str | None,
    fresh: bool,
    session_svg: bool,
    selected_style_names: tuple[str, ...] = (),
    progress: ProgressReporter,
    photos: PhotosBackend | None = None,
    desc_prompt_suffix: str | None = None,
    gen_prompt_suffix: str | None = None,
    aspect_ratio: str | None = None,
) -> PipelineResult:
    """Run the full resize → describe → style → generate pipeline.

    Returns a PipelineResult with the output path and run ID.
    """
    console.rule("[bold magenta]imagemine[/]")

    input_path, input_album_photo_id, input_export_dir, people_names = _resolve_input(
        image_path,
        input_album,
        photos=photos,
        log=lambda msg: console.print(f"  [dim]{msg}[/]"),
        err=err,
    )
    resized_path: pathlib.Path | None = None
    try:
        run_id = insert_run(conn, input_path)
        if input_album_photo_id:
            update_run(conn, run_id, input_album_photo_id=input_album_photo_id)

        image, resized_path = _step_resize(conn, run_id, input_path, output_dir, err)

        description = _step_describe(
            conn,
            console,
            run_id,
            image,
            desc_temp=desc_temp,
            anthropic_api_key=anthropic_api_key,
            claude_model=claude_model,
            story=story,
            desc_prompt_suffix=desc_prompt_suffix,
            people_names=people_names,
            progress=progress,
            err=err,
        )

        description = _step_style(
            conn,
            console,
            run_id,
            description,
            style=style,
            selected_style_names=selected_style_names,
            fresh=fresh,
            gen_prompt_suffix=gen_prompt_suffix,
        )

        output_path = _step_generate(
            conn,
            console,
            run_id,
            description,
            image,
            img_temp=img_temp,
            gemini_api_key=gemini_api_key,
            output_dir=output_dir,
            gemini_model=gemini_model,
            aspect_ratio=aspect_ratio,
            progress=progress,
            err=err,
        )

        added_to_album = _step_album_import(
            output_path,
            description,
            destination_album=destination_album,
            photos=photos,
            err=err,
        )

        total_s = time.monotonic() - t_start
        _print_summary(
            console,
            conn,
            run_id=run_id,
            total_s=total_s,
            input_path=input_path,
            input_album=input_album,
            output_path=output_path,
            destination_album=added_to_album,
        )

        if session_svg:
            svg_path = output_dir / f"imagemine_{run_id}.svg"
            console.save_svg(str(svg_path), title="imagemine")
            console.print(f"  [dim]Session saved:[/] [cyan]{svg_path}[/]")

        return PipelineResult(output_path=output_path, run_id=run_id)
    finally:
        if resized_path is not None:
            resized_path.unlink(missing_ok=True)
        if input_export_dir is not None:
            shutil.rmtree(input_export_dir, ignore_errors=True)
