"""Tests for _pipeline helper functions."""

from __future__ import annotations

import importlib
import pathlib
import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from rich.console import Console

from imagemine._db import init_db, insert_run

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable, Generator


def _get_pipeline():
    """Get the current pipeline module, handling module cache invalidation."""
    return importlib.import_module("imagemine._pipeline")


class FakeProgressReporter:
    """Minimal ProgressReporter for tests."""

    @contextmanager
    def step(
        self,
        spinner: str,
        color: str,
    ) -> Generator[Callable[[str], None]]:
        yield lambda _msg: None


class _FakePhotosBase:
    """Protocol-compliant base for test fakes."""

    def random_photo_from_album(
        self, album_name: str
    ) -> tuple[str, str, pathlib.Path, list[str]]:
        return "", "", pathlib.Path(), []

    def add_to_photos_album(
        self, output_path: str, album_name: str, description: str
    ) -> None:
        pass


# ---------------------------------------------------------------------------
# _validate_input
# ---------------------------------------------------------------------------


def test_validate_input_returns_resolved_path(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"img")
    m = _get_pipeline()
    result = m._validate_input(str(f), lambda msg: None)
    assert result == str(f.resolve())


def test_validate_input_exits_when_not_found() -> None:
    errors: list[str] = []
    m = _get_pipeline()
    with pytest.raises(SystemExit) as exc_info:
        m._validate_input("/nonexistent/photo.jpg", errors.append)
    assert exc_info.value.code == 1
    assert "not found" in errors[0]


def test_validate_input_exits_when_not_a_file(tmp_path: pathlib.Path) -> None:
    errors: list[str] = []
    m = _get_pipeline()
    with pytest.raises(SystemExit) as exc_info:
        m._validate_input(str(tmp_path), errors.append)
    assert exc_info.value.code == 1
    assert "Not a file" in errors[0]


# ---------------------------------------------------------------------------
# _resolve_input
# ---------------------------------------------------------------------------


def test_resolve_input_album_without_backend_exits() -> None:
    errors: list[str] = []
    m = _get_pipeline()
    with pytest.raises(SystemExit) as exc_info:
        m._resolve_input(
            None,
            "MyAlbum",
            photos=None,
            log=lambda _msg: None,
            err=errors.append,
        )
    assert exc_info.value.code == 1
    assert "No photos backend" in errors[0]


def test_resolve_input_no_path_no_album_exits() -> None:
    errors: list[str] = []
    m = _get_pipeline()
    with pytest.raises(SystemExit) as exc_info:
        m._resolve_input(
            None,
            None,
            photos=None,
            log=lambda _msg: None,
            err=errors.append,
        )
    assert exc_info.value.code == 1
    assert "Provide an image path" in errors[0]


# ---------------------------------------------------------------------------
# _step_album_import
# ---------------------------------------------------------------------------


def test_step_album_import_returns_none_without_album() -> None:
    m = _get_pipeline()
    result = m._step_album_import(
        "/out.png",
        "desc",
        destination_album=None,
        photos=None,
        err=lambda _msg: None,
    )
    assert result is None


def test_step_album_import_returns_album_name_on_success() -> None:
    m = _get_pipeline()
    result = m._step_album_import(
        "/out.png",
        "desc",
        destination_album="MyAlbum",
        photos=_FakePhotosBase(),
        err=lambda _msg: None,
    )
    assert result == "MyAlbum"


def test_step_album_import_returns_none_on_error() -> None:
    class FakePhotos(_FakePhotosBase):
        def add_to_photos_album(
            self, output_path: str, album_name: str, description: str
        ) -> None:
            msg = "fail"
            raise RuntimeError(msg)

    errors: list[str] = []
    m = _get_pipeline()
    result = m._step_album_import(
        "/out.png",
        "desc",
        destination_album="MyAlbum",
        photos=FakePhotos(),
        err=errors.append,
    )
    assert result is None
    assert "Failed to add" in errors[0]


# ---------------------------------------------------------------------------
# _resolve_input – success paths
# ---------------------------------------------------------------------------


def test_resolve_input_with_image_path(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"img")
    m = _get_pipeline()
    path, photo_id, export_dir, names = m._resolve_input(
        str(f),
        None,
        photos=None,
        log=lambda _: None,
        err=lambda _: None,
    )
    assert path == str(f.resolve())
    assert photo_id is None
    assert export_dir is None
    assert names == []


def test_resolve_input_album_success(tmp_path: pathlib.Path) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    photo = export_dir / "pic.jpg"
    photo.write_bytes(b"img")

    class FakePhotos(_FakePhotosBase):
        def random_photo_from_album(
            self, album_name: str
        ) -> tuple[str, str, pathlib.Path, list[str]]:
            return str(photo), "id123", export_dir, ["Alice", "Bob"]

    logs: list[str] = []
    m = _get_pipeline()
    path, photo_id, exp_dir, names = m._resolve_input(
        None,
        "TestAlbum",
        photos=FakePhotos(),
        log=logs.append,
        err=lambda _: None,
    )
    assert path == str(photo)
    assert photo_id == "id123"
    assert exp_dir == export_dir
    assert names == ["Alice", "Bob"]
    assert any("TestAlbum" in msg for msg in logs)


def test_resolve_input_album_exception_exits() -> None:
    class FakePhotos(_FakePhotosBase):
        def random_photo_from_album(
            self, album_name: str
        ) -> tuple[str, str, pathlib.Path, list[str]]:
            msg = "network error"
            raise RuntimeError(msg)

    errors: list[str] = []
    m = _get_pipeline()
    with pytest.raises(SystemExit) as exc_info:
        m._resolve_input(
            None,
            "FailAlbum",
            photos=FakePhotos(),
            log=lambda _: None,
            err=errors.append,
        )
    assert exc_info.value.code == 1
    assert "Failed to fetch" in errors[0]


# ---------------------------------------------------------------------------
# _step_resize
# ---------------------------------------------------------------------------


def test_step_resize_success(conn: sqlite3.Connection, tmp_path: pathlib.Path) -> None:
    run_id = insert_run(conn, "/input.jpg")
    fake_image = Image.new("RGB", (10, 10))
    resized_path = tmp_path / "resized.jpg"
    m = _get_pipeline()

    with patch.object(m, "resize_image", return_value=(fake_image, resized_path)):
        image, path = m._step_resize(
            conn, run_id, "/input.jpg", tmp_path, lambda _: None
        )

    assert image is fake_image
    assert path == resized_path
    row = conn.execute(
        "SELECT resized_file_path FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row[0] == str(resized_path)


def test_step_resize_failure_exits(
    conn: sqlite3.Connection, tmp_path: pathlib.Path
) -> None:
    run_id = insert_run(conn, "/input.jpg")
    errors: list[str] = []
    m = _get_pipeline()

    with (
        patch.object(m, "resize_image", side_effect=OSError("bad image")),
        pytest.raises(SystemExit) as exc_info,
    ):
        m._step_resize(conn, run_id, "/input.jpg", tmp_path, errors.append)

    assert exc_info.value.code == 1
    assert "Failed to open image" in errors[0]


# ---------------------------------------------------------------------------
# _step_style
# ---------------------------------------------------------------------------


@pytest.fixture
def style_conn() -> Generator[sqlite3.Connection]:
    c = init_db(":memory:")
    yield c
    c.close()


def _quiet_console() -> Console:
    return Console(quiet=True)


def test_step_style_with_style_and_selected_names(
    style_conn: sqlite3.Connection,
) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    m = _get_pipeline()
    result = m._step_style(
        style_conn,
        _quiet_console(),
        run_id,
        "A cat sitting",
        style="watercolor",
        selected_style_names=("Watercolor",),
        fresh=False,
        gen_prompt_suffix=None,
    )
    assert "Style: watercolor" in result
    row = style_conn.execute(
        "SELECT style FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row[0] == "watercolor"


def test_step_style_custom_style_without_selected_names(
    style_conn: sqlite3.Connection,
) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    m = _get_pipeline()
    result = m._step_style(
        style_conn,
        _quiet_console(),
        run_id,
        "A dog running",
        style="my custom style",
        selected_style_names=(),
        fresh=False,
        gen_prompt_suffix=None,
    )
    assert "Style: my custom style" in result


def test_step_style_random_fallback(style_conn: sqlite3.Connection) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    m = _get_pipeline()
    with patch.object(m, "random_style", return_value=("TestStyle", "test desc")):
        result = m._step_style(
            style_conn,
            _quiet_console(),
            run_id,
            "A bird flying",
            style=None,
            selected_style_names=(),
            fresh=False,
            gen_prompt_suffix=None,
        )
    assert "Style: TestStyle: test desc" in result


def test_step_style_fresh_uses_least_used(style_conn: sqlite3.Connection) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    m = _get_pipeline()
    with patch.object(m, "least_used_style", return_value=("FreshStyle", "fresh desc")):
        result = m._step_style(
            style_conn,
            _quiet_console(),
            run_id,
            "A tree",
            style=None,
            selected_style_names=(),
            fresh=True,
            gen_prompt_suffix=None,
        )
    assert "Style: FreshStyle: fresh desc" in result


def test_step_style_no_style_found(style_conn: sqlite3.Connection) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    m = _get_pipeline()
    with patch.object(m, "random_style", return_value=(None, None)):
        result = m._step_style(
            style_conn,
            _quiet_console(),
            run_id,
            "A tree",
            style=None,
            selected_style_names=(),
            fresh=False,
            gen_prompt_suffix=None,
        )
    assert result == "A tree"


def test_step_style_appends_gen_prompt_suffix(
    style_conn: sqlite3.Connection,
) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    m = _get_pipeline()
    result = m._step_style(
        style_conn,
        _quiet_console(),
        run_id,
        "A cat",
        style="bold",
        selected_style_names=(),
        fresh=False,
        gen_prompt_suffix="extra instructions",
    )
    assert result.endswith("extra instructions")


# ---------------------------------------------------------------------------
# _step_generate
# ---------------------------------------------------------------------------


def test_step_generate_delegates_and_returns_path(
    style_conn: sqlite3.Connection,
) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    fake_image = Image.new("RGB", (10, 10))
    m = _get_pipeline()

    with patch.object(m, "_run_generation", return_value="/output/gen.png"):
        result = m._step_generate(
            style_conn,
            _quiet_console(),
            run_id,
            "desc",
            fake_image,
            img_temp=1.0,
            gemini_api_key="key",
            output_dir=pathlib.Path("/output"),
            gemini_model="gemini-2.0",
            aspect_ratio=None,
            debug=False,
            progress=FakeProgressReporter(),
            err=lambda _: None,
        )
    assert result == "/output/gen.png"


def test_step_generate_aspect_ratio_defaults_to_4_3(
    style_conn: sqlite3.Connection,
) -> None:
    run_id = insert_run(style_conn, "/input.jpg")
    fake_image = Image.new("RGB", (10, 10))
    m = _get_pipeline()

    with patch.object(m, "_run_generation", return_value="/out.png") as mock:
        m._step_generate(
            style_conn,
            _quiet_console(),
            run_id,
            "desc",
            fake_image,
            img_temp=1.0,
            gemini_api_key="key",
            output_dir=pathlib.Path("/output"),
            gemini_model="gemini-2.0",
            aspect_ratio=None,
            debug=False,
            progress=FakeProgressReporter(),
            err=lambda _: None,
        )
    assert mock.call_args.kwargs["aspect_ratio"] == "4:3"


# ---------------------------------------------------------------------------
# run_pipeline – integration
# ---------------------------------------------------------------------------


def _patch_pipeline(m, **overrides):
    """Return a context manager that patches all external deps on the pipeline module."""
    from contextlib import ExitStack

    stack = ExitStack()
    defaults = {
        "resize_image": (
            Image.new("RGB", (10, 10)),
            pathlib.Path("/tmp/resized.jpg"),
        ),
        "_get_description": "A nice image",
        "_run_generation": "/out.png",
        "_print_summary": None,
        "random_style": (None, None),
    }
    defaults.update(overrides)
    mocks = {}
    for attr, rv in defaults.items():
        mocks[attr] = stack.enter_context(patch.object(m, attr, return_value=rv))
    return stack, mocks


def test_run_pipeline_full_flow(tmp_path: pathlib.Path) -> None:
    db_conn = init_db(":memory:")
    console = Console(quiet=True)
    input_file = tmp_path / "input.jpg"
    input_file.write_bytes(b"img")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    resized = tmp_path / "resized.jpg"
    resized.write_bytes(b"resized")
    output_path = str(output_dir / "gen.png")
    m = _get_pipeline()

    stack, _ = _patch_pipeline(
        m,
        resize_image=(Image.new("RGB", (10, 10)), resized),
        _run_generation=output_path,
        random_style=("Pop Art", "bold colors"),
    )
    with stack:
        result = m.run_pipeline(
            db_conn,
            console,
            err=lambda _: None,
            t_start=time.monotonic(),
            output_dir=output_dir,
            image_path=str(input_file),
            input_album=None,
            destination_album=None,
            desc_temp=0.5,
            img_temp=1.0,
            claude_model="claude-sonnet-4-6",
            gemini_model="gemini-2.0",
            anthropic_api_key="akey",
            gemini_api_key="gkey",
            story=None,
            style=None,
            fresh=False,
            session_svg=False,
            debug=False,
            progress=FakeProgressReporter(),
        )

    assert isinstance(result, m.PipelineResult)
    assert result.output_path == output_path
    assert result.run_id >= 1
    assert not resized.exists()
    db_conn.close()


def test_run_pipeline_strips_image_prefix(tmp_path: pathlib.Path) -> None:
    db_conn = init_db(":memory:")
    console = Console(quiet=True)
    input_file = tmp_path / "input.jpg"
    input_file.write_bytes(b"img")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    resized = tmp_path / "resized.jpg"
    resized.write_bytes(b"resized")
    m = _get_pipeline()

    stack, mocks = _patch_pipeline(
        m,
        resize_image=(Image.new("RGB", (10, 10)), resized),
        _get_description="PREAMBLE IMAGE: The actual description",
    )
    with stack:
        m.run_pipeline(
            db_conn,
            console,
            err=lambda _: None,
            t_start=time.monotonic(),
            output_dir=output_dir,
            image_path=str(input_file),
            input_album=None,
            destination_album=None,
            desc_temp=0.5,
            img_temp=1.0,
            claude_model="claude-sonnet-4-6",
            gemini_model="gemini-2.0",
            anthropic_api_key="akey",
            gemini_api_key="gkey",
            story=None,
            style=None,
            fresh=False,
            session_svg=False,
            debug=False,
            progress=FakeProgressReporter(),
        )

    desc_arg = mocks["_run_generation"].call_args.args[2]
    assert desc_arg == "The actual description"
    db_conn.close()


def test_run_pipeline_with_people_names(tmp_path: pathlib.Path) -> None:
    db_conn = init_db(":memory:")
    console = Console(quiet=True)
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    photo = export_dir / "pic.jpg"
    photo.write_bytes(b"img")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    resized = tmp_path / "resized.jpg"
    resized.write_bytes(b"resized")

    class FakePhotos(_FakePhotosBase):
        def random_photo_from_album(
            self, album_name: str
        ) -> tuple[str, str, pathlib.Path, list[str]]:
            return str(photo), "id123", export_dir, ["Alice"]

    m = _get_pipeline()
    stack, mocks = _patch_pipeline(
        m,
        resize_image=(Image.new("RGB", (10, 10)), resized),
        _get_description="A person smiling",
    )
    with stack:
        m.run_pipeline(
            db_conn,
            console,
            err=lambda _: None,
            t_start=time.monotonic(),
            output_dir=output_dir,
            image_path=None,
            input_album="TestAlbum",
            destination_album=None,
            desc_temp=0.5,
            img_temp=1.0,
            claude_model="claude-sonnet-4-6",
            gemini_model="gemini-2.0",
            anthropic_api_key="akey",
            gemini_api_key="gkey",
            story=None,
            style=None,
            fresh=False,
            session_svg=False,
            debug=False,
            progress=FakeProgressReporter(),
            photos=FakePhotos(),
        )

    desc_arg = mocks["_run_generation"].call_args.args[2]
    assert "Characters in the photo: Alice" in desc_arg
    db_conn.close()


def test_run_pipeline_saves_session_svg(tmp_path: pathlib.Path) -> None:
    db_conn = init_db(":memory:")
    console = MagicMock(spec=Console)
    console.print = MagicMock()
    console.rule = MagicMock()
    input_file = tmp_path / "input.jpg"
    input_file.write_bytes(b"img")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    resized = tmp_path / "resized.jpg"
    resized.write_bytes(b"resized")
    m = _get_pipeline()

    stack, _ = _patch_pipeline(
        m,
        resize_image=(Image.new("RGB", (10, 10)), resized),
        _get_description="desc",
    )
    with stack:
        result = m.run_pipeline(
            db_conn,
            console,
            err=lambda _: None,
            t_start=time.monotonic(),
            output_dir=output_dir,
            image_path=str(input_file),
            input_album=None,
            destination_album=None,
            desc_temp=0.5,
            img_temp=1.0,
            claude_model="claude-sonnet-4-6",
            gemini_model="gemini-2.0",
            anthropic_api_key="akey",
            gemini_api_key="gkey",
            story=None,
            style=None,
            fresh=False,
            session_svg=True,
            debug=False,
            progress=FakeProgressReporter(),
        )

    expected_svg = str(output_dir / f"imagemine_{result.run_id}.svg")
    console.save_svg.assert_called_once_with(expected_svg, title="imagemine")
    db_conn.close()
