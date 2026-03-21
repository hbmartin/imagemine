"""macOS Photos album integration via osascript."""

import pathlib
import shutil
import sqlite3
import subprocess
import tempfile

_IMAGE_SUFFIXES = frozenset(
    {".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"},
)


def _run_osascript(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Execute a static AppleScript with dynamic values passed via argv."""
    return subprocess.run(
        ["/usr/bin/osascript", "-e", script, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _add_to_photos_album(
    output_path: str,
    album_name: str,
    description: str = "",
) -> None:
    """Import a file into macOS Photos and add it to the named album."""
    script = """on run argv
    set outputPath to item 1 of argv
    set albumName to item 2 of argv
    set photoDescription to item 3 of argv
    tell application "Photos"
        set theAlbums to every album whose name is albumName
        if (count of theAlbums) = 0 then
            error "Photos album not found: " & albumName
        end if
        set importedItems to (import {POSIX file outputPath} into (first item of theAlbums) skip check duplicates yes)
        if photoDescription is not "" then
            if (count of importedItems) > 0 then
                set description of (first item of importedItems) to photoDescription
            end if
        end if
    end tell
end run"""
    result = _run_osascript(script, output_path, album_name, description)
    if result.returncode != 0:
        msg = f"Photos import failed for {output_path!r}: {result.stderr.strip()}"
        raise RuntimeError(msg)


_PHOTOS_DB = (
    pathlib.Path.home()
    / "Pictures"
    / "Photos Library.photoslibrary"
    / "database"
    / "Photos.sqlite"
)

_PEOPLE_QUERY = """\
SELECT ZPERSON.ZFULLNAME
FROM ZPERSON
JOIN ZDETECTEDFACE ON ZDETECTEDFACE.ZPERSONFORFACE = ZPERSON.Z_PK
JOIN ZASSET ON ZASSET.Z_PK = ZDETECTEDFACE.ZASSETFORFACE
WHERE ZASSET.ZUUID = ?
  AND ZPERSON.ZFULLNAME IS NOT NULL
"""


def _people_for_photo(photo_uuid: str) -> list[str]:
    """Look up recognised-person names for *photo_uuid* from the Photos DB."""
    uuid = photo_uuid.split("/", maxsplit=1)[0]
    if not _PHOTOS_DB.exists():
        return []
    try:
        conn = sqlite3.connect(
            f"file:{_PHOTOS_DB}?mode=ro",
            uri=True,
        )
        try:
            rows = conn.execute(_PEOPLE_QUERY, (uuid,)).fetchall()
        finally:
            conn.close()
    except (sqlite3.DatabaseError, OSError):
        return []
    people_names: set[str] = set()
    for row in rows:
        if (name_raw := row[0]) is None:
            continue
        if name := name_raw.strip():
            people_names.add(name)
    return sorted(people_names)


def _random_photo_from_album(
    album_name: str,
    max_attempts: int = 10,
) -> tuple[str, str, pathlib.Path, list[str]]:
    """Export a random still image from a macOS Photos album.

    Returns (exported_file_path, photos_item_id, export_dir, people_names).
    """
    base_script = """on run argv
    set albumName to item 1 of argv
    set exportDir to item 2 of argv
    tell application "Photos"
        set theAlbums to every album whose name is albumName
        if (count of theAlbums) = 0 then
            error "Photos album not found: " & albumName
        end if
        set theItems to media items of (first item of theAlbums)
        if (count of theItems) = 0 then
            error "Album is empty: " & albumName
        end if
        set idx to (random number from 1 to (count of theItems)) as integer
        set thePhoto to item idx of theItems
        export {thePhoto} to POSIX file exportDir
        return id of thePhoto
    end tell
end run"""

    for _ in range(max_attempts):
        tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="imagemine_input_"))
        result = _run_osascript(base_script, album_name, str(tmp_dir))
        if result.returncode != 0:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            stderr = result.stderr.strip()
            msg = f"Failed to fetch photo from album {album_name!r}: {stderr}"
            raise RuntimeError(msg)
        files = list(tmp_dir.iterdir())
        if not files:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            msg = f"No photo exported from album {album_name!r}"
            raise RuntimeError(msg)
        exported = next(
            (path for path in files if path.suffix.lower() in _IMAGE_SUFFIXES),
            None,
        )
        if exported is None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            continue
        photo_id = result.stdout.strip()
        people_names = _people_for_photo(photo_id)
        return str(exported), photo_id, tmp_dir, people_names

    msg = (
        f"Could not find a non-video photo in album {album_name!r}"
        f" after {max_attempts} attempts"
    )
    raise RuntimeError(msg)
