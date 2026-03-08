"""macOS Photos album integration via osascript."""

import pathlib
import subprocess
import tempfile


def _add_to_photos_album(
    output_path: str,
    album_name: str,
) -> None:
    """Import a file into macOS Photos and add it to the named album."""
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


def _random_photo_from_album(album_name: str) -> tuple[str, str]:
    """Export a random photo from a macOS Photos album.

    Returns (exported_file_path, photos_item_id).
    """
    tmp_dir = tempfile.mkdtemp(prefix="imagemine_input_")
    safe_album = album_name.replace("\\", "\\\\").replace('"', '\\"')
    script = "\n".join(
        [
            'tell application "Photos"',
            f'    set theAlbums to every album whose name is "{safe_album}"',
            "    if (count of theAlbums) = 0 then",
            f'        error "Photos album not found: {safe_album}"',
            "    end if",
            "    set theItems to media items of (first item of theAlbums)",
            "    if (count of theItems) = 0 then",
            f'        error "Album is empty: {safe_album}"',
            "    end if",
            "    set idx to (random number from 1 to (count of theItems)) as integer",
            "    set thePhoto to item idx of theItems",
            f'    export {{thePhoto}} to POSIX file "{tmp_dir}"',
            "    return id of thePhoto",
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
        msg = (
            f"Failed to fetch photo from album {album_name!r}: {result.stderr.strip()}"
        )
        raise RuntimeError(msg)
    files = list(pathlib.Path(tmp_dir).iterdir())
    if not files:
        msg = f"No photo exported from album {album_name!r}"
        raise RuntimeError(msg)
    photo_id = result.stdout.strip()
    return str(files[0]), photo_id
