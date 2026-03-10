"""Command-line interface for imagemine."""

import pathlib
import sys
import time

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
from ._pipeline import run_pipeline


def main() -> None:
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
    desc_prompt_suffix = _resolve_option(conn, None, "DESCRIPTION_PROMPT_SUFFIX")
    gen_prompt_suffix = _resolve_option(conn, None, "GENERATION_PROMPT_SUFFIX")

    run_pipeline(
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
        style=args.style,
        fresh=args.fresh,
        session_svg=args.session_svg,
        desc_prompt_suffix=desc_prompt_suffix,
        gen_prompt_suffix=gen_prompt_suffix,
    )
