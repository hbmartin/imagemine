"""Photos backend abstraction for album integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pathlib

from ._album import _add_to_photos_album, _random_photo_from_album


@runtime_checkable
class PhotosBackend(Protocol):
    """Protocol for album-based photo import/export."""

    def random_photo_from_album(
        self,
        album_name: str,
    ) -> tuple[str, str, pathlib.Path, list[str]]:
        """Return (file_path, photo_id, export_dir, people_names)."""
        ...

    def add_to_photos_album(
        self,
        output_path: str,
        album_name: str,
        description: str,
    ) -> None: ...


class MacOSPhotosBackend:
    """macOS Photos.app integration via osascript."""

    def random_photo_from_album(
        self,
        album_name: str,
    ) -> tuple[str, str, pathlib.Path, list[str]]:
        return _random_photo_from_album(album_name)

    def add_to_photos_album(
        self,
        output_path: str,
        album_name: str,
        description: str,
    ) -> None:
        _add_to_photos_album(output_path, album_name, description)
