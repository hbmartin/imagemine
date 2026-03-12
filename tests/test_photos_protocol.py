"""Tests for the PhotosBackend protocol and MacOSPhotosBackend."""

import imagemine._photos as photos_mod
from imagemine._photos import MacOSPhotosBackend, PhotosBackend


def test_macos_backend_satisfies_protocol() -> None:
    backend = MacOSPhotosBackend()
    assert isinstance(backend, PhotosBackend)


def test_macos_backend_add_delegates(monkeypatch) -> None:
    captured = []

    def fake_add(output_path, album_name, description):
        captured.append((output_path, album_name, description))

    monkeypatch.setattr(photos_mod, "_add_to_photos_album", fake_add)

    backend = MacOSPhotosBackend()
    backend.add_to_photos_album("/out.png", "Album", "desc")

    assert captured == [("/out.png", "Album", "desc")]


def test_macos_backend_random_photo_delegates(monkeypatch, tmp_path) -> None:
    def fake_random(album_name):
        return "/photo.jpg", "id-123", tmp_path, ["Alice"]

    monkeypatch.setattr(photos_mod, "_random_photo_from_album", fake_random)

    backend = MacOSPhotosBackend()
    path, photo_id, export_dir, people = backend.random_photo_from_album("Album")

    assert path == "/photo.jpg"
    assert photo_id == "id-123"
    assert export_dir == tmp_path
    assert people == ["Alice"]
