import importlib
import pathlib
import sys
import types
from types import SimpleNamespace


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

    try:
        cli._validate_input(missing, errors.append)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    assert errors == [f"Input file not found: {missing}"]


def test_validate_input_directory_calls_err_and_exits(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    errors = []

    try:
        cli._validate_input(str(tmp_path), errors.append)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    assert errors == [f"Not a file: {tmp_path}"]


# ---------------------------------------------------------------------------
# _resolve_input
# ---------------------------------------------------------------------------


def test_resolve_input_uses_image_path(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"fake")

    path, photo_id = cli._resolve_input(
        str(img), None, log=lambda _: None, err=lambda _: None
    )

    assert path == str(img.resolve())
    assert photo_id is None


def test_resolve_input_no_path_no_album_exits(monkeypatch) -> None:
    cli = _import_cli(monkeypatch)
    errors = []

    try:
        cli._resolve_input(None, None, log=lambda _: None, err=errors.append)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    assert len(errors) == 1


def test_resolve_input_image_path_takes_priority_over_album(
    monkeypatch, tmp_path
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
        str(img), "MyAlbum", log=lambda _: None, err=lambda _: None
    )

    assert path == str(img.resolve())
    assert photo_id is None
    assert album_calls == []


def test_main_style_preview_skips_gemini_api_key(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    resized_path = tmp_path / "resized.jpg"
    resized_path.write_bytes(b"fake")
    requested_keys = []

    class FakeStatus:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConsole:
        def __init__(self, *args, **kwargs):
            pass

        def print(self, *args, **kwargs):
            pass

        def rule(self, *args, **kwargs):
            pass

        def status(self, *args, **kwargs):
            return FakeStatus()

        def save_svg(self, *args, **kwargs):
            pass

    class FakeProgress:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def add_task(self, *args, **kwargs):
            return 1

        def update(self, *args, **kwargs):
            pass

    def fake_resolve_api_key(conn, key, prompt):
        requested_keys.append(key)
        return f"{key.lower()}-value"

    monkeypatch.setattr(
        cli,
        "_parse_args",
        lambda: SimpleNamespace(
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
        ),
    )
    monkeypatch.setattr(cli, "Console", FakeConsole)
    monkeypatch.setattr(cli, "Progress", FakeProgress)
    monkeypatch.setattr(cli, "init_db", lambda db_path: object())
    monkeypatch.setattr(cli, "_resolve_option", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *args, **kwargs: kwargs["default"],
    )
    monkeypatch.setattr(cli, "_resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(cli, "_resolve_input", lambda *args, **kwargs: (str(tmp_path / "photo.jpg"), None))
    monkeypatch.setattr(cli, "insert_run", lambda conn, input_path: 1)
    monkeypatch.setattr(cli, "update_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "resize_image", lambda input_path, output_dir: (object(), resized_path))
    monkeypatch.setattr(cli, "_get_description", lambda *args, **kwargs: "description")
    monkeypatch.setattr(
        cli,
        "_run_generation",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("generation should not run")),
    )

    cli.main()

    assert requested_keys == ["ANTHROPIC_API_KEY"]
    assert not resized_path.exists()


def test_main_launchd_rejects_non_positive_interval(monkeypatch, tmp_path) -> None:
    cli = _import_cli(monkeypatch)
    printed = []
    launchd_calls = []

    class FakeConsole:
        def __init__(self, *args, **kwargs):
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
    monkeypatch.setattr(cli, "Console", FakeConsole)
    monkeypatch.setattr(cli, "init_db", lambda db_path: object())
    monkeypatch.setattr(
        cli,
        "_write_launchd_plist",
        lambda **kwargs: launchd_calls.append(kwargs),
    )

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    assert launchd_calls == []
    assert printed == [
        (("[bold red]Error:[/] --launchd must be a positive integer.",), {})
    ]
