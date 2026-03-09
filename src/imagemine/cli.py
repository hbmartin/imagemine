"""Command-line interface for imagemine."""

import pathlib
import sys
import time

from rich.console import Console

from ._commands import dispatch_subcommand
from ._config import _parse_args
from ._constants import DEFAULT_DB_PATH
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

    run_pipeline(args, conn, console, err, t_start, output_dir)
