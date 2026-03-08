"""CLI argument parsing and config resolution."""

import argparse
import os
import sys
from typing import TYPE_CHECKING

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
        "--force",
        action="store_true",
        help="Ignore cached description and regenerate from scratch",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress all output",
    )
    return parser.parse_args()
