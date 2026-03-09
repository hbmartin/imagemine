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
