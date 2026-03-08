"""Command-line interface for imagemine."""

import argparse
import os
import pathlib
import sys
import time
from typing import TYPE_CHECKING

from ._core import DB_PATH, DESCRIPTION_MODEL, IMAGE_MODEL, resize_image
from ._db import (
    avg_duration_ms,
    get_config,
    init_db,
    insert_run,
    lookup_description,
    set_config,
    update_run,
)
from ._describe import describe_image
from ._generate import generate_image

if TYPE_CHECKING:
    import sqlite3


def _resolve_api_key(conn: sqlite3.Connection, key: str, prompt: str) -> str:
    value = get_config(conn, key) or os.environ.get(key)
    if not value:
        value = input(f"{prompt}: ").strip()
        if not value:
            print(f"Error: {key} is required.", file=sys.stderr)
            sys.exit(1)
        set_config(conn, key, value)
        print(f"{key} saved to database.", file=sys.stderr)
    return value


def _add_to_photos_album(output_path: str, album_name: str) -> None:
    try:
        from osxphotos.photosalbum import (  # noqa: PLC0415  # type: ignore[import-not-found]
            PhotosAlbum,
        )
    except ImportError:
        return
    PhotosAlbum(album_name).add(pathlib.Path(output_path))


def _resolve_temp(
    conn: sqlite3.Connection,
    cli_value: float | None,
    config_key: str,
) -> float:
    if cli_value is not None:
        return cli_value
    stored = get_config(conn, config_key)
    return float(stored) if stored is not None else 1.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform a photo into a fantasy image",
    )
    parser.add_argument("image_path", help="Path to input image")
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


def main() -> None:
    """Run the imagemine pipeline: resize, describe, generate."""
    args = _parse_args()

    def log(msg: str) -> None:
        if not args.silent:
            print(msg, file=sys.stderr)

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = str(pathlib.Path(args.image_path).resolve())

    conn = init_db(DB_PATH)
    desc_temp = _resolve_temp(conn, args.desc_temp, "DEFAULT_DESC_TEMP")
    img_temp = _resolve_temp(conn, args.img_temp, "DEFAULT_IMG_TEMP")
    anthropic_api_key = _resolve_api_key(
        conn,
        "ANTHROPIC_API_KEY",
        "Enter Anthropic API key",
    )
    gemini_api_key = _resolve_api_key(conn, "GEMINI_API_KEY", "Enter Gemini API key")
    run_id = insert_run(conn, input_path)

    log("Resizing image...")
    image, resized_path = resize_image(args.image_path, output_dir)
    update_run(conn, run_id, resized_file_path=str(resized_path))

    cached = None if args.force else lookup_description(conn, input_path)
    if cached:
        log("Reusing cached description from previous run.")
        description = cached
    else:
        avg = avg_duration_ms(conn, "desc_gen_ms")
        avg_str = f" (avg time: {avg / 1000:.1f}s)" if avg is not None else ""
        log(f"Generating fantastical description with Claude...{avg_str}")
        t0 = time.monotonic()
        description = describe_image(
            image,
            temperature=desc_temp,
            api_key=anthropic_api_key,
        )
        desc_gen_ms = round((time.monotonic() - t0) * 1000)
        update_run(
            conn,
            run_id,
            generated_description=description,
            description_model_name=DESCRIPTION_MODEL,
            desc_temp=desc_temp,
            desc_gen_ms=desc_gen_ms,
        )
    log(f"\nDescription:\n{description}\n")

    avg = avg_duration_ms(conn, "img_gen_ms")
    avg_str = f" (avg time: {avg / 1000:.1f}s)" if avg is not None else ""
    log(f"Generating fantasy image with Gemini...{avg_str}")
    t0 = time.monotonic()
    result = generate_image(
        description,
        image,
        api_key=gemini_api_key,
        temperature=img_temp,
    )
    img_gen_ms = round((time.monotonic() - t0) * 1000)

    if result is not None:
        output_path = str(getattr(result, "path", result))
        update_run(
            conn,
            run_id,
            output_image_path=output_path,
            image_model_name=IMAGE_MODEL,
            img_temp=img_temp,
            img_gen_ms=img_gen_ms,
        )
        destination_album = get_config(conn, "destination_album")
        if destination_album:
            _add_to_photos_album(output_path, destination_album)
            log(f"Added to Photos album: {destination_album}")
        if not args.silent:
            print(output_path)
    else:
        log("Image generation failed.")
