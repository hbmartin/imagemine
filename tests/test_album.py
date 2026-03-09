import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from imagemine._album import _random_photo_from_album


def test_random_photo_from_album_cleans_up_temp_dir_on_failure(monkeypatch, tmp_path):
    created_dirs = []

    def fake_mkdtemp(*_args, **_kwargs):
        path = tmp_path / "imagemine_input_test"
        path.mkdir()
        created_dirs.append(path)
        return str(path)

    monkeypatch.setattr("imagemine._album.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(
        "imagemine._album.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["osascript"],
            returncode=1,
            stdout="",
            stderr="boom",
        ),
    )

    with pytest.raises(RuntimeError, match="Failed to fetch photo from album"):
        _random_photo_from_album("Album")

    assert created_dirs == [tmp_path / "imagemine_input_test"]
    assert not created_dirs[0].exists()


def test_random_photo_from_album_skips_mov(monkeypatch, tmp_path):
    call_count = 0
    run_calls = 0

    def fake_mkdtemp(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        path = tmp_path / f"imagemine_input_{call_count}"
        path.mkdir()
        return str(path)

    def fake_run(*_args, **_kwargs):
        nonlocal run_calls
        run_calls += 1
        return subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout=f"photo-id-{call_count}",
            stderr="",
        )

    monkeypatch.setattr("imagemine._album.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr("imagemine._album.subprocess.run", fake_run)

    # First export contains both Live Photo artifacts; second produces a .jpg.
    def side_effect_iterdir(self):
        n = int(self.name.split("_")[-1])
        if n == 1:
            mov = self / "photo.mov"
            jpg = self / "photo.jpg"
            mov.touch()
            jpg.touch()
            return iter([mov, jpg])
        p = self / "photo.jpg"
        p.touch()
        return iter([p])

    monkeypatch.setattr(pathlib.Path, "iterdir", side_effect_iterdir)

    file_path, photo_id, export_dir = _random_photo_from_album("Album")

    assert call_count == 1
    assert run_calls == 1
    assert file_path.endswith(".jpg")
    assert photo_id == "photo-id-1"
    assert export_dir.exists()


def test_random_photo_from_album_raises_after_max_mov_attempts(monkeypatch, tmp_path):
    call_count = 0
    run_calls = 0

    def fake_mkdtemp(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        path = tmp_path / f"imagemine_input_{call_count}"
        path.mkdir()
        return str(path)

    def fake_run(*_a, **_k):
        nonlocal run_calls
        run_calls += 1
        return subprocess.CompletedProcess(
            args=["osascript"], returncode=0, stdout="photo-id", stderr=""
        )

    monkeypatch.setattr("imagemine._album.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr("imagemine._album.subprocess.run", fake_run)

    def always_mov(self):
        p = self / "clip.mov"
        p.touch()
        return iter([p])

    monkeypatch.setattr(pathlib.Path, "iterdir", always_mov)

    with pytest.raises(RuntimeError, match="Could not find a non-video photo"):
        _random_photo_from_album("Album", max_attempts=3)

    assert call_count == 3
    assert run_calls == 3
