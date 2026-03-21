"""Tests for _pipeline helper functions."""

import pathlib

import pytest

from imagemine._pipeline import _resolve_input, _step_album_import, _validate_input

# ---------------------------------------------------------------------------
# _validate_input
# ---------------------------------------------------------------------------


def test_validate_input_returns_resolved_path(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"img")
    result = _validate_input(str(f), lambda msg: None)
    assert result == str(f.resolve())


def test_validate_input_exits_when_not_found() -> None:
    errors: list[str] = []
    with pytest.raises(SystemExit) as exc_info:
        _validate_input("/nonexistent/photo.jpg", errors.append)
    assert exc_info.value.code == 1
    assert "not found" in errors[0]


def test_validate_input_exits_when_not_a_file(tmp_path: pathlib.Path) -> None:
    errors: list[str] = []
    with pytest.raises(SystemExit) as exc_info:
        _validate_input(str(tmp_path), errors.append)
    assert exc_info.value.code == 1
    assert "Not a file" in errors[0]


# ---------------------------------------------------------------------------
# _resolve_input
# ---------------------------------------------------------------------------


def test_resolve_input_album_without_backend_exits() -> None:
    errors: list[str] = []
    with pytest.raises(SystemExit) as exc_info:
        _resolve_input(
            None,
            "MyAlbum",
            photos=None,
            log=lambda _msg: None,
            err=errors.append,
        )
    assert exc_info.value.code == 1
    assert "No photos backend" in errors[0]


def test_resolve_input_no_path_no_album_exits() -> None:
    errors: list[str] = []
    with pytest.raises(SystemExit) as exc_info:
        _resolve_input(
            None,
            None,
            photos=None,
            log=lambda _msg: None,
            err=errors.append,
        )
    assert exc_info.value.code == 1
    assert "Provide an image path" in errors[0]


# ---------------------------------------------------------------------------
# _step_album_import
# ---------------------------------------------------------------------------


def test_step_album_import_returns_none_without_album() -> None:
    result = _step_album_import(
        "/out.png",
        "desc",
        destination_album=None,
        photos=None,
        err=lambda _msg: None,
    )
    assert result is None


def test_step_album_import_returns_album_name_on_success() -> None:
    class FakePhotos:
        def add_to_photos_album(self, path, album, desc):
            pass

    result = _step_album_import(
        "/out.png",
        "desc",
        destination_album="MyAlbum",
        photos=FakePhotos(),
        err=lambda _msg: None,
    )
    assert result == "MyAlbum"


def test_step_album_import_returns_none_on_error() -> None:
    class FakePhotos:
        def add_to_photos_album(self, path, album, desc):
            msg = "fail"
            raise RuntimeError(msg)

    errors: list[str] = []
    result = _step_album_import(
        "/out.png",
        "desc",
        destination_album="MyAlbum",
        photos=FakePhotos(),
        err=errors.append,
    )
    assert result is None
    assert "Failed to add" in errors[0]
