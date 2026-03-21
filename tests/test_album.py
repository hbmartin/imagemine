import pathlib
import sqlite3
import subprocess

import pytest

from imagemine._album import (
    _add_to_photos_album,
    _people_for_photo,
    _random_photo_from_album,
)


def test_add_to_photos_album_passes_values_via_osascript_argv(monkeypatch, tmp_path):
    output_path = tmp_path / "generated image.png"
    output_path.write_bytes(b"generated")
    album_name = 'Album"\nset injected to true'
    description = 'Line one\nline two "quoted"'
    captured_args = []

    def fake_run(args, **_kwargs):
        captured_args.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("imagemine._album.subprocess.run", fake_run)

    _add_to_photos_album(str(output_path), album_name, description)

    assert len(captured_args) == 1
    script = captured_args[0][2]
    assert captured_args[0][3:] == [str(output_path), album_name, description]
    assert album_name not in script
    assert description not in script


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


def test_random_photo_from_album_passes_album_name_via_osascript_argv(
    monkeypatch,
    tmp_path,
):
    created_dirs = []
    captured_args = []
    album_name = 'Album"\nset injected to true'

    def fake_mkdtemp(*_args, **_kwargs):
        path = tmp_path / "imagemine_input_test"
        path.mkdir()
        created_dirs.append(path)
        return str(path)

    def fake_run(args, **_kwargs):
        captured_args.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="boom",
        )

    monkeypatch.setattr("imagemine._album.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr("imagemine._album.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Failed to fetch photo from album"):
        _random_photo_from_album(album_name)

    assert len(captured_args) == 1
    script = captured_args[0][2]
    assert captured_args[0][3:] == [album_name, str(created_dirs[0])]
    assert album_name not in script
    assert not created_dirs[0].exists()


def test_random_photo_from_album_skips_mov_and_sidecars(monkeypatch, tmp_path):
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
    monkeypatch.setattr(
        "imagemine._album._people_for_photo",
        lambda _uuid: ["Alice", "Bob"],
    )

    def side_effect_iterdir(self):
        mov = self / "photo.mov"
        aae = self / "photo.aae"
        jpg = self / "photo.jpg"
        mov.touch()
        aae.touch()
        jpg.touch()
        return iter([mov, aae, jpg])

    monkeypatch.setattr(pathlib.Path, "iterdir", side_effect_iterdir)

    file_path, photo_id, export_dir, people_names = _random_photo_from_album("Album")

    assert call_count == 1
    assert run_calls == 1
    assert file_path.endswith(".jpg")
    assert photo_id == "photo-id-1"
    assert export_dir.exists()
    assert people_names == ["Alice", "Bob"]


def test_random_photo_from_album_raises_after_max_mov_attempts(monkeypatch, tmp_path):
    call_count = 0
    max_attempts = 3
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
            args=["osascript"],
            returncode=0,
            stdout="photo-id",
            stderr="",
        )

    monkeypatch.setattr("imagemine._album.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr("imagemine._album.subprocess.run", fake_run)

    def always_mov(self):
        p = self / "clip.mov"
        p.touch()
        return iter([p])

    monkeypatch.setattr(pathlib.Path, "iterdir", always_mov)

    with pytest.raises(RuntimeError, match="Could not find a non-video photo"):
        _random_photo_from_album("Album", max_attempts=max_attempts)

    assert call_count == max_attempts
    assert run_calls == max_attempts


def test_add_to_photos_album_raises_on_nonzero_return(monkeypatch):
    monkeypatch.setattr(
        "imagemine._album.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["osascript"],
            returncode=1,
            stdout="",
            stderr="album not found",
        ),
    )

    with pytest.raises(RuntimeError, match="Photos import failed.*album not found"):
        _add_to_photos_album("/out.png", "NoAlbum", "desc")


def test_random_photo_from_album_raises_when_no_files_exported(monkeypatch, tmp_path):
    def fake_mkdtemp(*_args, **_kwargs):
        path = tmp_path / "imagemine_empty"
        path.mkdir()
        return str(path)

    monkeypatch.setattr("imagemine._album.tempfile.mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(
        "imagemine._album.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="photo-id",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        pathlib.Path,
        "iterdir",
        lambda self: iter([]),
    )

    with pytest.raises(RuntimeError, match="No photo exported from album"):
        _random_photo_from_album("Album")


def test_people_for_photo_returns_empty_when_db_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "imagemine._album._PHOTOS_DB",
        tmp_path / "nonexistent" / "Photos.sqlite",
    )

    result = _people_for_photo("some-uuid/version")

    assert result == []


def test_people_for_photo_returns_names_from_db(monkeypatch, tmp_path):
    db_path = tmp_path / "Photos.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE ZASSET (Z_PK INTEGER PRIMARY KEY, ZUUID TEXT)",
    )
    conn.execute(
        "CREATE TABLE ZPERSON (Z_PK INTEGER PRIMARY KEY, ZFULLNAME TEXT)",
    )
    conn.execute(
        "CREATE TABLE ZDETECTEDFACE"
        " (Z_PK INTEGER PRIMARY KEY, ZPERSONFORFACE INTEGER, ZASSETFORFACE INTEGER)",
    )
    conn.execute("INSERT INTO ZASSET (Z_PK, ZUUID) VALUES (1, 'abc-123')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (10, 'Alice')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (11, 'Bob')")
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (100, 10, 1)",
    )
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (101, 11, 1)",
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("imagemine._album._PHOTOS_DB", db_path)

    result = _people_for_photo("abc-123/version-id")

    assert sorted(result) == ["Alice", "Bob"]


def test_people_for_photo_strips_whitespace_and_skips_empty_names(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "Photos.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE ZASSET (Z_PK INTEGER PRIMARY KEY, ZUUID TEXT)",
    )
    conn.execute(
        "CREATE TABLE ZPERSON (Z_PK INTEGER PRIMARY KEY, ZFULLNAME TEXT)",
    )
    conn.execute(
        "CREATE TABLE ZDETECTEDFACE"
        " (Z_PK INTEGER PRIMARY KEY, ZPERSONFORFACE INTEGER, ZASSETFORFACE INTEGER)",
    )
    conn.execute("INSERT INTO ZASSET (Z_PK, ZUUID) VALUES (1, 'trim-test')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (10, '  Alice  ')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (11, '   ')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (12, 'Alice')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (13, 'Bob')")
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (100, 10, 1)",
    )
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (101, 11, 1)",
    )
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (102, 12, 1)",
    )
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (103, 13, 1)",
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("imagemine._album._PHOTOS_DB", db_path)

    result = _people_for_photo("trim-test")

    assert result == ["Alice", "Bob"]


def test_people_for_photo_handles_db_error(monkeypatch, tmp_path):
    db_path = tmp_path / "corrupt.sqlite"
    db_path.write_bytes(b"not a database")

    monkeypatch.setattr("imagemine._album._PHOTOS_DB", db_path)

    result = _people_for_photo("some-uuid")

    assert result == []


def test_people_for_photo_strips_uuid_slash(monkeypatch, tmp_path):
    db_path = tmp_path / "Photos.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE ZASSET (Z_PK INTEGER PRIMARY KEY, ZUUID TEXT)",
    )
    conn.execute(
        "CREATE TABLE ZPERSON (Z_PK INTEGER PRIMARY KEY, ZFULLNAME TEXT)",
    )
    conn.execute(
        "CREATE TABLE ZDETECTEDFACE"
        " (Z_PK INTEGER PRIMARY KEY, ZPERSONFORFACE INTEGER, ZASSETFORFACE INTEGER)",
    )
    conn.execute("INSERT INTO ZASSET (Z_PK, ZUUID) VALUES (1, 'uuid-only')")
    conn.execute("INSERT INTO ZPERSON (Z_PK, ZFULLNAME) VALUES (10, 'Charlie')")
    conn.execute(
        "INSERT INTO ZDETECTEDFACE (Z_PK, ZPERSONFORFACE, ZASSETFORFACE)"
        " VALUES (100, 10, 1)",
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("imagemine._album._PHOTOS_DB", db_path)

    assert _people_for_photo("uuid-only/L0/001") == ["Charlie"]
    assert _people_for_photo("uuid-only") == ["Charlie"]
