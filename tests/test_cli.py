import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest
from rich.console import Console


def _install_import_stubs(monkeypatch) -> None:
    root = pathlib.Path(__file__).resolve().parents[1] / "src"
    monkeypatch.syspath_prepend(str(root))

    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = object
    anthropic_types = types.ModuleType("anthropic.types")
    anthropic_beta = types.ModuleType("anthropic.types.beta")

    class BetaTextBlock:
        pass

    anthropic_beta.BetaTextBlock = BetaTextBlock

    gemimg = types.ModuleType("gemimg")
    gemimg.GemImg = object

    class ImageGen:
        image_path = "generated.png"

    gemimg.ImageGen = ImageGen

    pil = types.ModuleType("PIL")

    class ImageModule:
        class Image:
            pass

        class Resampling:
            LANCZOS = object()

    class FakePngInfo:
        def add_text(self, *_args, **_kwargs):
            pass

    class PngImagePluginModule:
        PngInfo = FakePngInfo

    pil.Image = ImageModule
    pil.PngImagePlugin = PngImagePluginModule

    monkeypatch.setitem(sys.modules, "anthropic", anthropic)
    monkeypatch.setitem(sys.modules, "anthropic.types", anthropic_types)
    monkeypatch.setitem(sys.modules, "anthropic.types.beta", anthropic_beta)
    monkeypatch.setitem(sys.modules, "gemimg", gemimg)
    monkeypatch.setitem(sys.modules, "PIL", pil)


def _clear_imagemine_modules() -> None:
    for module_name in tuple(sys.modules):
        if module_name == "imagemine" or module_name.startswith("imagemine."):
            sys.modules.pop(module_name, None)


def _import_cli(monkeypatch):
    _install_import_stubs(monkeypatch)
    _clear_imagemine_modules()
    return importlib.import_module("imagemine.cli")


def _import_pipeline(monkeypatch):
    _install_import_stubs(monkeypatch)
    _clear_imagemine_modules()
    return importlib.import_module("imagemine._pipeline")


def _base_args(tmp_path, **overrides) -> SimpleNamespace:
    values = {
        "image_path": str(tmp_path / "photo.jpg"),
        "input_album": None,
        "output_dir": str(tmp_path / "out"),
        "desc_temp": None,
        "img_temp": None,
        "destination_album": None,
        "story": None,
        "style": None,
        "fresh": False,
        "list_styles": False,
        "add_style": False,
        "remove_style": False,
        "silent": False,
        "history": False,
        "config": False,
        "session_svg": False,
        "config_path": None,
        "launchd": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _pipeline_kwargs(**overrides) -> dict:
    """Return a minimal set of explicit run_pipeline keyword arguments."""
    defaults = {
        "image_path": None,
        "input_album": None,
        "destination_album": None,
        "desc_temp": 1.0,
        "img_temp": 1.0,
        "claude_model": "claude-model",
        "gemini_model": "gemini-model",
        "anthropic_api_key": "key",
        "gemini_api_key": "key",
        "story": None,
        "style": None,
        "fresh": False,
        "session_svg": False,
    }
    defaults.update(overrides)
    return defaults


def test_validate_input_returns_resolved_path(monkeypatch, tmp_path) -> None:
    pipeline = _import_pipeline(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")
    errors = []

    result = pipeline._validate_input(str(img), errors.append)

    assert result == str(img.resolve())
    assert errors == []


def test_validate_input_missing_file_calls_err_and_exits(monkeypatch, tmp_path) -> None:
    pipeline = _import_pipeline(monkeypatch)
    missing = str(tmp_path / "missing.jpg")
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        pipeline._validate_input(missing, errors.append)
    assert exc_info.value.code == 1
    assert errors == [f"Input file not found: {missing}"]


def test_validate_input_directory_calls_err_and_exits(monkeypatch, tmp_path) -> None:
    pipeline = _import_pipeline(monkeypatch)
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        pipeline._validate_input(str(tmp_path), errors.append)
    assert exc_info.value.code == 1
    assert errors == [f"Not a file: {tmp_path}"]


def test_resolve_input_uses_image_path(monkeypatch, tmp_path) -> None:
    pipeline = _import_pipeline(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")

    path, photo_id, export_dir = pipeline._resolve_input(
        str(img),
        None,
        log=lambda _: None,
        err=lambda _: None,
    )

    assert path == str(img.resolve())
    assert photo_id is None
    assert export_dir is None


def test_resolve_input_no_path_no_album_exits(monkeypatch) -> None:
    pipeline = _import_pipeline(monkeypatch)
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        pipeline._resolve_input(None, None, log=lambda _: None, err=errors.append)
    assert exc_info.value.code == 1
    assert errors == ["Provide an image path or configure INPUT_ALBUM"]


def test_resolve_input_image_path_takes_priority_over_album(
    monkeypatch,
    tmp_path,
) -> None:
    pipeline = _import_pipeline(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")
    album_calls = []

    def fake_random_photo(album_name):
        album_calls.append(album_name)
        return "/from/album.jpg", "photo-id-123", tmp_path / "album-export"

    monkeypatch.setattr(pipeline, "_random_photo_from_album", fake_random_photo)

    path, photo_id, export_dir = pipeline._resolve_input(
        str(img),
        "MyAlbum",
        log=lambda _: None,
        err=lambda _: None,
    )

    assert path == str(img.resolve())
    assert photo_id is None
    assert export_dir is None
    assert album_calls == []


def test_resolve_input_album_returns_cleanup_dir(monkeypatch, tmp_path) -> None:
    pipeline = _import_pipeline(monkeypatch)
    export_dir = tmp_path / "album-export"
    export_dir.mkdir()

    monkeypatch.setattr(
        pipeline,
        "_random_photo_from_album",
        lambda _album_name: ("/from/album.jpg", "photo-id-123", export_dir),
    )

    path, photo_id, cleanup_dir = pipeline._resolve_input(
        None,
        "MyAlbum",
        log=lambda _: None,
        err=lambda _: None,
    )

    assert path == "/from/album.jpg"
    assert photo_id == "photo-id-123"
    assert cleanup_dir == export_dir


def test_run_pipeline_cleans_up_temp_files_and_logs_album_import_failure(
    monkeypatch,
    tmp_path,
) -> None:
    pipeline = _import_pipeline(monkeypatch)
    export_dir = tmp_path / "album-export"
    export_dir.mkdir()
    exported_file = export_dir / "input.jpg"
    exported_file.write_bytes(b"input")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    resized_path = output_dir / "input_resized.jpg"
    resized_path.write_bytes(b"resized")
    output_path = output_dir / "generated.png"
    output_path.write_bytes(b"generated")
    updates = []
    summary_calls = []

    monkeypatch.setattr(
        pipeline,
        "_resolve_input",
        lambda *_args, **_kwargs: (str(exported_file), "photo-id-123", export_dir),
    )
    monkeypatch.setattr(pipeline, "insert_run", lambda *_args, **_kwargs: 7)
    monkeypatch.setattr(
        pipeline,
        "update_run",
        lambda _conn, run_id, **kwargs: updates.append((run_id, kwargs)),
    )
    monkeypatch.setattr(
        pipeline,
        "resize_image",
        lambda *_args, **_kwargs: (object(), resized_path),
    )
    monkeypatch.setattr(pipeline, "_get_description", lambda *_args, **_kwargs: "desc")
    monkeypatch.setattr(
        pipeline,
        "random_style",
        lambda *_args, **_kwargs: (None, None),
    )
    monkeypatch.setattr(
        pipeline,
        "_run_generation",
        lambda *_args, **_kwargs: str(output_path),
    )
    monkeypatch.setattr(
        pipeline,
        "_print_summary",
        lambda *args: summary_calls.append(args),
    )
    monkeypatch.setattr(
        pipeline,
        "_add_to_photos_album",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("import failed")),
    )

    errors = []

    pipeline.run_pipeline(
        object(),
        Console(quiet=True),
        errors.append,
        0.0,
        output_dir,
        **_pipeline_kwargs(input_album="Album", destination_album="Dest"),
    )

    assert errors == ["Failed to add to Photos album 'Dest': import failed"]
    assert len(summary_calls) == 1
    assert not resized_path.exists()
    assert not export_dir.exists()
    assert updates[0] == (7, {"input_album_photo_id": "photo-id-123"})
    assert updates[1] == (7, {"resized_file_path": str(resized_path)})


def test_run_pipeline_cleans_up_export_dir_if_insert_run_fails(
    monkeypatch,
    tmp_path,
) -> None:
    pipeline = _import_pipeline(monkeypatch)
    export_dir = tmp_path / "album-export"
    export_dir.mkdir()
    exported_file = export_dir / "input.jpg"
    exported_file.write_bytes(b"input")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    monkeypatch.setattr(
        pipeline,
        "_resolve_input",
        lambda *_args, **_kwargs: (str(exported_file), "photo-id-123", export_dir),
    )
    monkeypatch.setattr(
        pipeline,
        "insert_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db failed")),
    )

    with pytest.raises(RuntimeError, match="db failed"):
        pipeline.run_pipeline(
            object(),
            Console(quiet=True),
            lambda _msg: None,
            0.0,
            output_dir,
            **_pipeline_kwargs(input_album="Album"),
        )

    assert not export_dir.exists()


def test_main_stops_when_subcommand_is_handled(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    args = _base_args(tmp_path)
    init_db_calls = []
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(
        cli,
        "init_db",
        lambda db_path: init_db_calls.append(db_path) or object(),
    )
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: True)
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *run_args, **run_kwargs: pipeline_calls.append((run_args, run_kwargs)),
    )

    cli.main()

    assert init_db_calls == [cli.DEFAULT_DB_PATH]
    assert pipeline_calls == []
    assert pathlib.Path(args.output_dir).is_dir()


def test_main_runs_pipeline_with_resolved_paths(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    args = _base_args(
        tmp_path,
        output_dir="relative-output",
        config_path="~/custom/imagemine.db",
    )
    init_db_calls = []
    pipeline_calls = []
    fake_conn = object()

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(
        cli,
        "init_db",
        lambda db_path: init_db_calls.append(db_path) or fake_conn,
    )
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(cli, "_resolve_option", lambda *_a, **_kw: None)
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *run_args, **run_kwargs: pipeline_calls.append((run_args, run_kwargs)),
    )

    cli.main()

    assert init_db_calls == [pathlib.Path(args.config_path).expanduser()]
    assert len(pipeline_calls) == 1
    positional, _kwargs = pipeline_calls[0]
    conn, _console, _err, t_start, output_dir = positional
    assert conn is fake_conn
    assert isinstance(t_start, float)
    assert output_dir == pathlib.Path(args.output_dir).resolve()


def test_main_passes_story_to_pipeline(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    args = _base_args(tmp_path, story="some story")
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(cli, "_resolve_option", lambda *_a, **_kw: None)
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *run_args, **run_kwargs: pipeline_calls.append((run_args, run_kwargs)),
    )

    cli.main()

    assert len(pipeline_calls) == 1
    _positional, kwargs = pipeline_calls[0]
    assert kwargs["story"] == "some story"
