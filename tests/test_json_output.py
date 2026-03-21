"""Tests for --json output mode and --silent path-only output."""

import importlib
import json
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest


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


class _FakeConsole:
    def __init__(self) -> None:
        self.print_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def print(self, *args, **kwargs) -> None:
        self.print_calls.append((args, kwargs))

    def print_exception(self, **kwargs) -> None:
        pass


def test_json_output_prints_valid_json(monkeypatch, tmp_path, capsys) -> None:
    cli = _import_cli(monkeypatch)
    pipeline_module = importlib.import_module("imagemine._pipeline")

    args = SimpleNamespace(
        silent=False,
        json_output=True,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album=None,
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=False,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: _FakeConsole())
    monkeypatch.setattr(cli, "init_db", lambda _db_path: _make_fake_conn())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")

    fake_result = pipeline_module.PipelineResult(
        output_path="/tmp/out/generated.png",
        run_id=42,
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **_kwargs: fake_result,
    )

    # Fake DB query for run data
    class FakeConn:
        def execute(self, _query, _params=()):
            return SimpleNamespace(
                fetchone=lambda: (1500, 2500, "story text", "Watercolor: soft edges"),
            )

    monkeypatch.setattr(cli, "init_db", lambda _db_path: FakeConn())

    cli.main()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["output_path"] == "/tmp/out/generated.png"
    assert data["run_id"] == 42
    assert data["description"] == "story text"
    assert data["style"] == "Watercolor: soft edges"
    assert data["desc_gen_ms"] == 1500
    assert data["img_gen_ms"] == 2500
    assert isinstance(data["total_s"], float)


def test_silent_prints_only_path(monkeypatch, tmp_path, capsys) -> None:
    cli = _import_cli(monkeypatch)
    pipeline_module = importlib.import_module("imagemine._pipeline")

    args = SimpleNamespace(
        silent=True,
        json_output=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album=None,
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=False,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: _FakeConsole())
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")

    fake_result = pipeline_module.PipelineResult(
        output_path="/tmp/out/generated.png",
        run_id=42,
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **_kwargs: fake_result,
    )

    cli.main()

    captured = capsys.readouterr()
    assert captured.out.strip() == "/tmp/out/generated.png"


def test_choose_style_sets_style_kwarg(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)

    args = SimpleNamespace(
        silent=False,
        json_output=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album=None,
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=True,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: _FakeConsole())
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(
        cli,
        "_run_choose_style",
        lambda _conn: SimpleNamespace(
            style_prompt="Watercolor: soft edges",
            style_names=("Watercolor",),
        ),
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **kwargs: pipeline_calls.append(kwargs),
    )

    cli.main()

    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["style"] == "Watercolor: soft edges"
    assert pipeline_calls[0]["selected_style_names"] == ("Watercolor",)


def test_choose_style_blend_passes_all_selected_names(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    args = SimpleNamespace(
        silent=False,
        json_output=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album=None,
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=True,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: _FakeConsole())
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(
        cli,
        "_run_choose_style",
        lambda _conn: SimpleNamespace(
            style_prompt=("Watercolor: soft edges; Neon Noir: rain-slicked streets"),
            style_names=("Watercolor", "Neon Noir"),
        ),
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **kwargs: pipeline_calls.append(kwargs),
    )

    cli.main()

    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["style"] == (
        "Watercolor: soft edges; Neon Noir: rain-slicked streets"
    )
    assert pipeline_calls[0]["selected_style_names"] == (
        "Watercolor",
        "Neon Noir",
    )


def test_cli_skips_photos_backend_without_album_options(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    args = SimpleNamespace(
        silent=False,
        json_output=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album=None,
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=False,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: _FakeConsole())
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(
        cli,
        "MacOSPhotosBackend",
        lambda: (_ for _ in ()).throw(AssertionError("backend should not be built")),
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **kwargs: pipeline_calls.append(kwargs),
    )

    cli.main()

    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["photos"] is None


def test_cli_constructs_photos_backend_when_album_requested(
    monkeypatch,
    tmp_path,
) -> None:
    cli = _import_cli(monkeypatch)
    args = SimpleNamespace(
        silent=False,
        json_output=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album="Camera Roll",
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=False,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )
    backend = object()
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: _FakeConsole())
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli, "MacOSPhotosBackend", lambda: backend)
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **kwargs: pipeline_calls.append(kwargs),
    )

    cli.main()

    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["photos"] is backend


def test_cli_album_support_requires_macos(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    fake_console = _FakeConsole()
    args = SimpleNamespace(
        silent=False,
        json_output=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path="photo.jpg",
        input_album="Camera Roll",
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        choose_style=False,
        fresh=False,
        aspect_ratio=None,
        debug=False,
    )
    pipeline_calls = []

    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "Console", lambda **_kwargs: fake_console)
    monkeypatch.setattr(cli, "init_db", lambda _db_path: object())
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_a, default, **_kw: default,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda _conn, cli_value, *_args, **_kwargs: cli_value,
    )
    monkeypatch.setattr(cli, "_resolve_api_key", lambda *_a: "key")
    monkeypatch.setattr(cli.sys, "platform", "linux")
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **kwargs: pipeline_calls.append(kwargs),
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert pipeline_calls == []
    assert any(
        "Photos album support requires macOS." in str(args[0])
        for args, _kwargs in fake_console.print_calls
        if args
    )


def _make_fake_conn():
    return SimpleNamespace(
        execute=lambda *_a, **_kw: SimpleNamespace(fetchone=lambda: None),
    )
