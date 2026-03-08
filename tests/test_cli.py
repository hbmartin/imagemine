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


def test_add_to_photos_album_imports_before_assigning_album(monkeypatch) -> None:
    cli = _import_cli(monkeypatch)
    events = []
    album = object()
    log_messages = []

    class FakeLibrary:
        def album(self, name: str):
            events.append(("album_lookup", name))
            return album

        def import_photos(self, paths, skip_duplicate_check=True):
            msg = "unexpected import call signature"
            raise AssertionError(msg)

    photoscript = types.ModuleType("photoscript")
    photoscript.PhotosLibrary = FakeLibrary

    monkeypatch.setitem(sys.modules, "photoscript", photoscript)
    sys.modules.pop("osxphotos", None)
    sys.modules.pop("osxphotos.photosalbum", None)

    def import_photos(self, paths, *, album=None, skip_duplicate_check=True):
        events.append(("import", list(paths), album, skip_duplicate_check))
        return [object()]

    FakeLibrary.import_photos = import_photos

    cli._add_to_photos_album(
        "/tmp/output.png",
        "Album",
        log=log_messages.append,
    )

    assert events == [
        ("album_lookup", "Album"),
        ("import", ["/tmp/output.png"], album, True),
    ]


def test_add_to_photos_album_raises_when_album_is_missing(monkeypatch) -> None:
    cli = _import_cli(monkeypatch)

    class FakeLibrary:
        def album(self, name: str):
            return None

    photoscript = types.ModuleType("photoscript")
    photoscript.PhotosLibrary = FakeLibrary

    monkeypatch.setitem(sys.modules, "photoscript", photoscript)
    sys.modules.pop("osxphotos", None)
    sys.modules.pop("osxphotos.photosalbum", None)

    try:
        cli._add_to_photos_album("/tmp/output.png", "Album")
    except ValueError as exc:
        assert str(exc) == "Photos album not found: Album"
    else:
        msg = "expected ValueError"
        raise AssertionError(msg)


def test_add_to_photos_album_raises_when_import_fails(monkeypatch) -> None:
    cli = _import_cli(monkeypatch)
    album = object()

    class FakeLibrary:
        def album(self, name: str):
            return album

        def import_photos(self, paths, *, album=None, skip_duplicate_check=True):
            return []

    photoscript = types.ModuleType("photoscript")
    photoscript.PhotosLibrary = FakeLibrary

    monkeypatch.setitem(sys.modules, "photoscript", photoscript)
    sys.modules.pop("osxphotos", None)
    sys.modules.pop("osxphotos.photosalbum", None)

    try:
        cli._add_to_photos_album("/tmp/output.png", "Album")
    except RuntimeError as exc:
        assert str(exc) == "Photos import failed for: /tmp/output.png"
    else:
        msg = "expected RuntimeError"
        raise AssertionError(msg)
