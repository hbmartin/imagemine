import importlib
import pathlib
import sys
import types


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

    pil.Image = ImageModule

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
