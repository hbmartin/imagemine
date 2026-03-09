import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest


def _noop(*_args, **_kwargs) -> None:
    pass


class _FakeStatus:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConsole:
    def __init__(self, *_args, **_kwargs):
        pass

    def print(self, *_args, **_kwargs):
        pass

    def rule(self, *_args, **_kwargs):
        pass

    def status(self, *_args, **_kwargs):
        return _FakeStatus()

    def save_svg(self, *_args, **_kwargs):
        pass


class _FakeProgress:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, *_args, **_kwargs):
        return 1

    def update(self, *_args, **_kwargs):
        pass


def _style_preview_args(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        image_path=str(tmp_path / "photo.jpg"),
        input_album=None,
        output_dir=str(tmp_path),
        desc_temp=None,
        img_temp=None,
        destination_album=None,
        style="Risograph print",
        list_styles=False,
        add_style=False,
        silent=False,
        history=False,
        config=False,
        session_svg=False,
        config_path=None,
        launchd=None,
    )


def _patch_style_preview_dependencies(
    cli,
    monkeypatch,
    tmp_path,
    resized_path,
    requested_keys: list[str],
) -> None:
    def fake_resolve_api_key(_conn, key, _prompt):
        requested_keys.append(key)
        return f"{key.lower()}-value"

    def fake_resolve_required_option(*_args, **kwargs):
        return kwargs["default"]

    def fake_resolve_input(*_args, **_kwargs):
        return str(tmp_path / "photo.jpg"), None

    def fake_insert_run(_conn, _input_path):
        return 1

    def fake_resize_image(_input_path, _output_dir):
        return object(), resized_path

    def fake_get_description(*_args, **_kwargs):
        return "description"

    def fake_run_generation(*_args, **_kwargs):
        msg = "generation should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(cli, "_parse_args", lambda: _style_preview_args(tmp_path))
    monkeypatch.setattr(cli, "Console", _FakeConsole)
    monkeypatch.setattr(cli, "Progress", _FakeProgress)
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "_resolve_option", _noop)
    monkeypatch.setattr(cli, "_resolve_required_option", fake_resolve_required_option)
    monkeypatch.setattr(cli, "_resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(cli, "_resolve_input", fake_resolve_input)
    monkeypatch.setattr(cli, "insert_run", fake_insert_run)
    monkeypatch.setattr(cli, "update_run", _noop)
    monkeypatch.setattr(cli, "resize_image", fake_resize_image)
    monkeypatch.setattr(cli, "_get_description", fake_get_description)
    monkeypatch.setattr(cli, "_run_generation", fake_run_generation)


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

    pil = types.ModuleType("PIL")

    class ImageModule:
        class Image:
            pass

        class Resampling:
            LANCZOS = object()

    class FakePngInfo:
        def add_text(self, *args, **kwargs):
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


def _import_cli(monkeypatch):
    _install_import_stubs(monkeypatch)
    for module_name in (
        "imagemine.cli",
        "imagemine._core",
        "imagemine._image",
        "imagemine._describe",
        "imagemine._generate",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("imagemine.cli")


# ---------------------------------------------------------------------------
# _validate_input
# ---------------------------------------------------------------------------


def test_validate_input_returns_resolved_path(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")
    errors = []

    result = cli._validate_input(str(img), errors.append)

    assert result == str(img.resolve())
    assert errors == []


def test_validate_input_missing_file_calls_err_and_exits(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    missing = str(tmp_path / "missing.jpg")
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        cli._validate_input(missing, errors.append)
    assert exc_info.value.code == 1
    assert errors == [f"Input file not found: {missing}"]


def test_validate_input_directory_calls_err_and_exits(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        cli._validate_input(str(tmp_path), errors.append)
    assert exc_info.value.code == 1
    assert errors == [f"Not a file: {tmp_path}"]


# ---------------------------------------------------------------------------
# _resolve_input
# ---------------------------------------------------------------------------


def test_resolve_input_uses_image_path(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")

    path, photo_id = cli._resolve_input(
        str(img), None, log=lambda _: None, err=lambda _: None,
    )

    assert path == str(img.resolve())
    assert photo_id is None


def test_resolve_input_no_path_no_album_exits(monkeypatch) -> None:
    cli = _import_cli(monkeypatch)
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        cli._resolve_input(None, None, log=lambda _: None, err=errors.append)
    assert exc_info.value.code == 1
    assert len(errors) == 1


def test_resolve_input_image_path_takes_priority_over_album(
    monkeypatch, tmp_path,
) -> None:
    cli = _import_cli(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")
    album_calls = []

    def fake_random_photo(album_name):
        album_calls.append(album_name)
        return "/from/album.jpg", "photo-id-123"

    monkeypatch.setattr(
        importlib.import_module("imagemine._album"),
        "_random_photo_from_album",
        fake_random_photo,
    )

    path, photo_id = cli._resolve_input(
        str(img), "MyAlbum", log=lambda _: None, err=lambda _: None,
    )

    assert path == str(img.resolve())
    assert photo_id is None
    assert album_calls == []


def test_main_style_preview_skips_gemini_api_key(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    resized_path = tmp_path / "resized.jpg"
    resized_path.write_bytes(b"fake")
    requested_keys = []

    _patch_style_preview_dependencies(
        cli,
        monkeypatch,
        tmp_path,
        resized_path,
        requested_keys,
    )

    cli.main()

    assert requested_keys == ["ANTHROPIC_API_KEY"]
    assert not resized_path.exists()


def test_main_launchd_rejects_non_positive_interval(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    printed = []
    launchd_calls = []

    class CaptureConsole:
        def __init__(self, *_args, **_kwargs):
            pass

        def print(self, *args, **kwargs):
            printed.append((args, kwargs))

    monkeypatch.setattr(
        cli,
        "_parse_args",
        lambda: SimpleNamespace(
            image_path=None,
            input_album=None,
            output_dir=str(tmp_path),
            desc_temp=None,
            img_temp=None,
            destination_album=None,
            style=None,
            list_styles=False,
            add_style=False,
            silent=False,
            history=False,
            config=False,
            session_svg=False,
            config_path=None,
            launchd=0,
        ),
    )
    monkeypatch.setattr(cli, "Console", CaptureConsole)
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(
        cli,
        "_write_launchd_plist",
        lambda **kwargs: launchd_calls.append(kwargs),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 1
    assert launchd_calls == []
    assert printed == [
        (("[bold red]Error:[/] --launchd must be a positive integer.",), {}),
    ]
