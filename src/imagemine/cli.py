"""Command-line interface for imagemine."""

import json
import pathlib
import sys
import time
from typing import TYPE_CHECKING

from rich.console import Console

from ._commands import dispatch_subcommand
from ._config import (
    _parse_args,
    _resolve_api_key,
    _resolve_option,
    _resolve_required_option,
)
from ._constants import DEFAULT_DB_PATH, DEFAULT_DESCRIPTION_MODEL, DEFAULT_IMAGE_MODEL
from ._db import init_db
from ._photos import MacOSPhotosBackend
from ._pipeline import run_pipeline
from ._progress import NullProgressReporter, RichProgressReporter
from ._styles import _run_choose_style

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._photos import PhotosBackend


def _resolve_photos_backend(
    *,
    input_album: str | None,
    destination_album: str | None,
    err: Callable[[str], None],
) -> PhotosBackend | None:
    """Create the Photos backend only when album features are requested."""
    if input_album is None and destination_album is None:
        return None
    if sys.platform != "darwin":
        err("Photos album support requires macOS.")
        sys.exit(1)
    return MacOSPhotosBackend()


def main() -> None:
    """Run the imagemine pipeline: resize, describe, generate."""
    args = _parse_args()
    t_start = time.monotonic()
    quiet = args.silent or args.json_output
    console = Console(quiet=quiet, record=args.session_svg)

    def err(msg: str) -> None:
        console.print(f"[bold red]Error:[/] {msg}")
        if sys.exc_info()[0] is not None:
            console.print_exception(show_locals=False)

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = (
        pathlib.Path(args.config_path).expanduser()
        if args.config_path
        else DEFAULT_DB_PATH
    )
    conn = init_db(db_path)

    if dispatch_subcommand(args, conn, console, err):
        return

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
    gemini_api_key = _resolve_api_key(conn, "GEMINI_API_KEY", "Enter Gemini API key")
    desc_prompt_suffix = _resolve_option(
        conn,
        None,
        "DESCRIPTION_PROMPT_SUFFIX",
        env_key="DESCRIPTION_PROMPT_SUFFIX",
    )
    gen_prompt_suffix = _resolve_option(
        conn,
        None,
        "GENERATION_PROMPT_SUFFIX",
        env_key="GENERATION_PROMPT_SUFFIX",
    )
    aspect_ratio = _resolve_option(
        conn,
        args.aspect_ratio,
        "ASPECT_RATIO",
        env_key="ASPECT_RATIO",
    )

    style = args.style
    selected_style_names: tuple[str, ...] = ()
    if args.choose_style and style is None:
        chosen_style = _run_choose_style(conn)
        style = chosen_style.style_prompt
        selected_style_names = chosen_style.style_names

    progress = NullProgressReporter() if quiet else RichProgressReporter(console)
    photos = _resolve_photos_backend(
        input_album=input_album,
        destination_album=destination_album,
        err=err,
    )

    result = run_pipeline(
        conn,
        console,
        err,
        t_start,
        output_dir,
        image_path=args.image_path,
        input_album=input_album,
        destination_album=destination_album,
        desc_temp=desc_temp,
        img_temp=img_temp,
        claude_model=claude_model,
        gemini_model=gemini_model,
        anthropic_api_key=anthropic_api_key,
        gemini_api_key=gemini_api_key,
        story=args.story,
        style=style,
        selected_style_names=selected_style_names,
        fresh=args.fresh,
        session_svg=args.session_svg,
        debug=args.debug,
        progress=progress,
        photos=photos,
        desc_prompt_suffix=desc_prompt_suffix,
        gen_prompt_suffix=gen_prompt_suffix,
        aspect_ratio=aspect_ratio,
    )

    if args.json_output:
        run_data = conn.execute(
            "SELECT desc_gen_ms, img_gen_ms, generated_description, style"
            " FROM runs WHERE id = ?",
            (result.run_id,),
        ).fetchone()
        desc_ms, img_ms, description, run_style = run_data or (None, None, None, None)
        total_s = time.monotonic() - t_start
        print(
            json.dumps(
                {
                    "output_path": result.output_path,
                    "run_id": result.run_id,
                    "description": description,
                    "style": run_style,
                    "desc_gen_ms": desc_ms,
                    "img_gen_ms": img_ms,
                    "total_s": round(total_s, 2),
                },
            ),
        )
    elif args.silent:
        print(result.output_path)
