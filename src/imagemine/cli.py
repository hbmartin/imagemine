"""Command-line interface for imagemine."""

import pathlib
import sys
from typing import TYPE_CHECKING

from ._config import _parse_args, _resolve_api_key, _resolve_option
from ._core import DB_PATH, resize_image
from ._db import init_db, insert_run, update_run
from ._describe import _get_description
from ._generate import _run_generation

if TYPE_CHECKING:
    from collections.abc import Callable


def _add_to_photos_album(
    output_path: str,
    album_name: str,
) -> None:
    """Import a file into macOS Photos and add it to the named album."""
    import subprocess  # noqa: PLC0415

    safe_album = album_name.replace("\\", "\\\\").replace('"', '\\"')
    safe_path = output_path.replace("\\", "\\\\").replace('"', '\\"')
    script = "\n".join(
        [
            'tell application "Photos"',
            f'    set theAlbums to every album whose name is "{safe_album}"',
            "    if (count of theAlbums) = 0 then",
            f'        error "Photos album not found: {safe_album}"',
            "    end if",
            f'    import {{POSIX file "{safe_path}"}} '
            "into (first item of theAlbums) skip check duplicates yes",
            "end tell",
        ],
    )
    result = subprocess.run(  # noqa: S603
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"Photos import failed for {output_path!r}: {result.stderr.strip()}"
        raise RuntimeError(msg)


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


def main() -> None:
    """Run the imagemine pipeline: resize, describe, generate."""
    args = _parse_args()

    def log(msg: str) -> None:
        if not args.silent:
            print(msg, file=sys.stderr)

    def err(msg: str) -> None:
        print(f"Error: {msg}", file=sys.stderr)

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = _validate_input(args.image_path, err)

    conn = init_db(DB_PATH)
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
    run_id = insert_run(conn, input_path)

    log("Resizing image...")
    try:
        image, resized_path = resize_image(args.image_path, output_dir)
    except Exception as e:  # noqa: BLE001
        err(f"Failed to open image: {e}")
        sys.exit(1)
    update_run(conn, run_id, resized_file_path=str(resized_path))

    description = _get_description(
        conn,
        run_id,
        image,
        input_path,
        desc_temp,
        anthropic_api_key,
        force=args.force,
        log=log,
        err=err,
    )
    log(f"\nDescription:\n{description}\n")

    output_path = _run_generation(
        conn,
        run_id,
        description,
        image,
        img_temp,
        gemini_api_key,
        output_dir,
        log=log,
        err=err,
    )
    if destination_album:
        try:
            _add_to_photos_album(output_path, str(destination_album))
            log(f"Added to Photos album: {destination_album}")
        except Exception as e:  # noqa: BLE001
            err(f"Failed to add to Photos album {destination_album!r}: {e}")
