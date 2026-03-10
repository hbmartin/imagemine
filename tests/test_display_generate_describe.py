import runpy
import sys
from types import SimpleNamespace

import pytest
from PIL import Image
from rich.console import Console

import imagemine._describe as describe
import imagemine._display as display
import imagemine._generate as generate


def test_module_main_delegates_to_cli(monkeypatch) -> None:
    calls = []

    monkeypatch.setitem(
        sys.modules,
        "imagemine.cli",
        SimpleNamespace(main=lambda: calls.append("called")),
    )

    runpy.run_module("imagemine.__main__", run_name="__main__")

    assert calls == ["called"]


def test_show_history_prints_empty_state(monkeypatch) -> None:
    console = Console(record=True)

    monkeypatch.setattr(display, "get_recent_runs", lambda _conn: [])

    display._show_history(object(), console)

    assert "No runs found." in console.export_text()


def test_show_history_formats_runs(monkeypatch) -> None:
    console = Console(record=True, width=200)
    runs = [
        (
            "2026-03-09T12:34:56",
            "/tmp/photo.jpg",
            "Watercolor",
            "1500",
            "500",
            "/tmp/out.png",
        ),
        (
            "invalid-date",
            None,
            None,
            None,
            None,
            None,
        ),
    ]

    monkeypatch.setattr(display, "get_recent_runs", lambda _conn: runs)

    display._show_history(object(), console)

    rendered = console.export_text()
    assert "photo.jpg" in rendered
    assert "Watercolor" in rendered
    assert "1.5s" in rendered
    assert "0.5s" in rendered
    assert "2.0s" in rendered
    assert "out.png" in rendered
    assert "invalid-date" in rendered


def test_show_styles_prints_empty_state(monkeypatch) -> None:
    console = Console(record=True)

    monkeypatch.setattr(display, "get_all_styles", lambda _conn: [])

    display._show_styles(object(), console)

    assert "No styles found." in console.export_text()


def test_show_styles_formats_rows(monkeypatch) -> None:
    console = Console(record=True)
    styles = [
        ("Watercolor", "soft edges", 2, "2026-03-09T12:34:56"),
        ("Sketch", "rough lines", 0, "not-a-date"),
    ]

    monkeypatch.setattr(display, "get_all_styles", lambda _conn: styles)

    display._show_styles(object(), console)

    rendered = console.export_text()
    assert "Styles" in rendered
    assert "Watercolor" in rendered
    assert "soft edges" in rendered
    assert "Sketch" in rendered
    assert "not-a-date" in rendered
    assert "Total: 2 styles" in rendered


def test_print_summary_renders_style_and_timings(conn) -> None:
    console = Console(record=True)
    run_id = 1
    conn.execute(
        "INSERT INTO runs (id, desc_gen_ms, img_gen_ms) VALUES (?, ?, ?)",
        (run_id, 1250, 2500),
    )
    conn.commit()

    display._print_summary(
        console,
        conn,
        run_id=run_id,
        total_s=4.2,
        input_path="/tmp/input/photo.jpg",
        input_album=None,
        output_path="/tmp/output.png",
    )

    rendered = console.export_text()
    assert "Done" in rendered
    assert "photo.jpg" in rendered
    assert "1.2s" in rendered
    assert "2.5s" in rendered
    assert "4.2s" in rendered
    assert "/tmp/output.png" in rendered


def test_generate_image_uses_gemimg(monkeypatch) -> None:
    captured = {}

    class FakeGemImg:
        def __init__(self, *, model: str, api_key: str) -> None:
            captured["init"] = (model, api_key)

        def generate(
            self,
            description,
            image,
            *,
            aspect_ratio: str,
            temperature: float,
            save_dir: str,
        ):
            captured["generate"] = (
                description,
                image,
                aspect_ratio,
                temperature,
                save_dir,
            )
            return "result"

    monkeypatch.setattr(generate, "GemImg", FakeGemImg)

    image = object()
    result = generate.generate_image(
        "prompt",
        image,
        api_key="api-key",
        temperature=1.4,
        save_dir="/tmp/out",
        model="gemini-custom",
    )

    assert captured["init"] == ("gemini-custom", "api-key")
    assert captured["generate"] == ("prompt", image, "4:3", 1.4, "/tmp/out")
    assert result == "result"


def test_run_generation_updates_db_and_metadata(monkeypatch, tmp_path) -> None:
    class FakeImageGen:
        def __init__(self, image_path: str) -> None:
            self.image_path = image_path

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    output_path = output_dir / "generated.png"
    output_path.write_bytes(b"png")
    logs = []
    updates = []
    metadata_calls = []
    monotonic_values = iter((10.0, 11.25))

    monkeypatch.setattr(generate, "ImageGen", FakeImageGen)
    monkeypatch.setattr(generate, "avg_duration_ms", lambda _conn, _column: 2000.0)
    monkeypatch.setattr(
        generate,
        "generate_image",
        lambda *_args, **_kwargs: FakeImageGen("generated.png"),
    )
    monkeypatch.setattr(
        generate,
        "write_png_metadata",
        lambda path, description: metadata_calls.append((path, description)),
    )
    monkeypatch.setattr(
        generate,
        "update_run",
        lambda _conn, run_id, **kwargs: updates.append((run_id, kwargs)),
    )
    monkeypatch.setattr(
        generate.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    result = generate._run_generation(
        object(),
        5,
        "prompt text",
        object(),
        img_temp=0.8,
        api_key="api-key",
        output_dir=output_dir,
        model="gemini-custom",
        log=logs.append,
        err=lambda _msg: None,
    )

    assert result == str(output_path)
    assert logs == [
        "Generating image with Gemini... (avg time: 2.0s)",
        f"Image written to: {output_path}",
    ]
    assert metadata_calls == [(str(output_path), "prompt text")]
    assert updates == [
        (
            5,
            {
                "output_image_path": str(output_path),
                "image_model_name": "gemini-custom",
                "img_temp": 0.8,
                "img_gen_ms": 1250,
            },
        ),
    ]


def test_run_generation_exits_on_generation_exception(monkeypatch, tmp_path) -> None:
    errors = []
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    monkeypatch.setattr(generate, "avg_duration_ms", lambda _conn, _column: None)
    monkeypatch.setattr(
        generate,
        "generate_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(SystemExit) as exc_info:
        generate._run_generation(
            object(),
            5,
            "prompt",
            object(),
            img_temp=0.8,
            api_key="api-key",
            output_dir=output_dir,
            log=lambda _msg: None,
            err=errors.append,
        )

    assert exc_info.value.code == 1
    assert errors == ["Image generation failed: boom"]


def test_run_generation_exits_when_result_is_none(monkeypatch, tmp_path) -> None:
    errors = []
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    monkeypatch.setattr(generate, "avg_duration_ms", lambda _conn, _column: None)
    monkeypatch.setattr(generate, "generate_image", lambda *_args, **_kwargs: None)

    with pytest.raises(SystemExit) as exc_info:
        generate._run_generation(
            object(),
            5,
            "prompt",
            object(),
            img_temp=0.8,
            api_key="api-key",
            output_dir=output_dir,
            log=lambda _msg: None,
            err=errors.append,
        )

    assert exc_info.value.code == 1
    assert errors == ["Image generation returned no result."]


def test_run_generation_exits_on_unexpected_result(monkeypatch, tmp_path) -> None:
    errors = []
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    class FakeImageGen:
        def __init__(self, image_path: str | None) -> None:
            self.image_path = image_path

    monkeypatch.setattr(generate, "ImageGen", FakeImageGen)
    monkeypatch.setattr(generate, "avg_duration_ms", lambda _conn, _column: None)
    monkeypatch.setattr(
        generate,
        "generate_image",
        lambda *_args, **_kwargs: FakeImageGen(None),
    )

    with pytest.raises(SystemExit) as exc_info:
        generate._run_generation(
            object(),
            5,
            "prompt",
            object(),
            img_temp=0.8,
            api_key="api-key",
            output_dir=output_dir,
            log=lambda _msg: None,
            err=errors.append,
        )

    assert exc_info.value.code == 1
    assert len(errors) == 1
    assert errors[0].startswith("Image generation returned unexpected result:")


def test_run_generation_exits_when_output_is_missing(monkeypatch, tmp_path) -> None:
    errors = []
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    class FakeImageGen:
        def __init__(self, image_path: str) -> None:
            self.image_path = image_path

    monkeypatch.setattr(generate, "ImageGen", FakeImageGen)
    monkeypatch.setattr(generate, "avg_duration_ms", lambda _conn, _column: None)
    monkeypatch.setattr(
        generate,
        "generate_image",
        lambda *_args, **_kwargs: FakeImageGen("missing.png"),
    )

    with pytest.raises(SystemExit) as exc_info:
        generate._run_generation(
            object(),
            5,
            "prompt",
            object(),
            img_temp=0.8,
            api_key="api-key",
            output_dir=output_dir,
            log=lambda _msg: None,
            err=errors.append,
        )

    assert exc_info.value.code == 1
    assert errors == [
        f"Generated image not found at expected path: {output_dir / 'missing.png'}",
    ]


def test_describe_image_uploads_and_returns_text(monkeypatch) -> None:
    create_calls = []
    deleted = []
    uploaded_paths = []

    class FakeBetaTextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeFiles:
        def upload(self, *, file, betas):
            uploaded_paths.append((file, tuple(betas)))
            return SimpleNamespace(id="file-123")

        def delete(self, file_id: str, *, betas) -> None:
            deleted.append((file_id, tuple(betas)))

    class FakeMessages:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(content=[FakeBetaTextBlock("story text")])

    class FakeClient:
        def __init__(self) -> None:
            self.beta = SimpleNamespace(
                files=FakeFiles(),
                messages=FakeMessages(),
            )

    monkeypatch.setattr(describe, "BetaTextBlock", FakeBetaTextBlock)
    monkeypatch.setattr(
        describe.anthropic,
        "Anthropic",
        lambda api_key=None: FakeClient(),
    )

    result = describe.describe_image(
        Image.new("RGB", (10, 10), color="red"),
        temperature=1.7,
        api_key="anthropic-key",
        model="claude-custom",
        story="Extra detail",
    )

    assert result == "story text"
    uploaded_file, betas = uploaded_paths[0]
    assert uploaded_file.suffix == ".jpg"
    assert betas == ("files-api-2025-04-14",)
    assert not uploaded_file.exists()
    assert create_calls[0]["model"] == "claude-custom"
    assert create_calls[0]["temperature"] == 1.7
    assert "Extra detail" in create_calls[0]["messages"][0]["content"][1]["text"]
    assert deleted == [("file-123", ("files-api-2025-04-14",))]


def test_describe_image_appends_prompt_suffix(monkeypatch) -> None:
    create_calls = []

    class FakeBetaTextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeFiles:
        def upload(self, *, file, betas):
            return SimpleNamespace(id="file-123")

        def delete(self, file_id: str, *, betas) -> None:
            return None

    class FakeMessages:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(content=[FakeBetaTextBlock("story text")])

    class FakeClient:
        def __init__(self) -> None:
            self.beta = SimpleNamespace(
                files=FakeFiles(),
                messages=FakeMessages(),
            )

    monkeypatch.setattr(describe, "BetaTextBlock", FakeBetaTextBlock)
    monkeypatch.setattr(
        describe.anthropic,
        "Anthropic",
        lambda api_key=None: FakeClient(),
    )

    describe.describe_image(
        Image.new("RGB", (10, 10), color="red"),
        prompt_suffix="Use vivid colors",
    )

    prompt_text = create_calls[0]["messages"][0]["content"][1]["text"]
    assert "Use vivid colors" in prompt_text


def test_describe_image_raises_when_no_text_block(monkeypatch) -> None:
    deleted = []

    class FakeBetaTextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class NonTextBlock:
        pass

    class FakeFiles:
        def upload(self, *, file, betas):
            return SimpleNamespace(id="file-999")

        def delete(self, file_id: str, *, betas) -> None:
            deleted.append((file_id, tuple(betas)))

    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(content=[NonTextBlock()])

    class FakeClient:
        def __init__(self) -> None:
            self.beta = SimpleNamespace(
                files=FakeFiles(),
                messages=FakeMessages(),
            )

    monkeypatch.setattr(describe, "BetaTextBlock", FakeBetaTextBlock)
    monkeypatch.setattr(
        describe.anthropic,
        "Anthropic",
        lambda api_key=None: FakeClient(),
    )

    with pytest.raises(TypeError, match="No text block found in response"):
        describe.describe_image(Image.new("RGB", (10, 10), color="blue"))

    assert deleted == [("file-999", ("files-api-2025-04-14",))]


def test_get_description_updates_db(monkeypatch) -> None:
    logs = []
    updates = []
    monotonic_values = iter((20.0, 21.5))

    monkeypatch.setattr(describe, "avg_duration_ms", lambda _conn, _column: 3000.0)
    monkeypatch.setattr(
        describe,
        "describe_image",
        lambda *_args, **_kwargs: "story text",
    )
    monkeypatch.setattr(
        describe,
        "update_run",
        lambda _conn, run_id, **kwargs: updates.append((run_id, kwargs)),
    )
    monkeypatch.setattr(
        describe.time,
        "monotonic",
        lambda: next(monotonic_values),
    )

    result = describe._get_description(
        object(),
        9,
        Image.new("RGB", (5, 5), color="green"),
        desc_temp=1.2,
        api_key="api-key",
        model="claude-custom",
        story="story prompt",
        log=logs.append,
        err=lambda _msg: None,
    )

    assert result == "story text"
    assert logs == ["Generating storyline with Claude... (avg time: 3.0s)"]
    assert updates == [
        (
            9,
            {
                "generated_description": "story text",
                "description_model_name": "claude-custom",
                "desc_temp": 1.2,
                "desc_gen_ms": 1500,
            },
        ),
    ]


def test_get_description_passes_prompt_suffix(monkeypatch) -> None:
    describe_calls: list[dict[str, object]] = []

    monkeypatch.setattr(describe, "avg_duration_ms", lambda _conn, _column: None)
    monkeypatch.setattr(
        describe,
        "describe_image",
        lambda *_args, **kwargs: describe_calls.append(kwargs) or "story text",
    )
    monkeypatch.setattr(describe, "update_run", lambda _conn, run_id, **kwargs: None)

    describe._get_description(
        object(),
        9,
        Image.new("RGB", (5, 5), color="green"),
        desc_temp=1.2,
        api_key="api-key",
        model="claude-custom",
        story="story prompt",
        prompt_suffix="custom suffix",
        log=lambda _msg: None,
        err=lambda _msg: None,
    )

    assert describe_calls == [
        {
            "temperature": 1.2,
            "api_key": "api-key",
            "model": "claude-custom",
            "story": "story prompt",
            "prompt_suffix": "custom suffix",
        },
    ]


def test_get_description_exits_on_failure(monkeypatch) -> None:
    errors = []

    monkeypatch.setattr(describe, "avg_duration_ms", lambda _conn, _column: None)
    monkeypatch.setattr(
        describe,
        "describe_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(SystemExit) as exc_info:
        describe._get_description(
            object(),
            9,
            Image.new("RGB", (5, 5), color="yellow"),
            desc_temp=1.2,
            api_key="api-key",
            log=lambda _msg: None,
            err=errors.append,
        )

    assert exc_info.value.code == 1
    assert errors == ["Description generation failed: boom"]
