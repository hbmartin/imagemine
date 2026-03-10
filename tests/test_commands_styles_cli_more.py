import importlib
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest

import imagemine._commands as commands
import imagemine._config as cfg
import imagemine._styles as styles
from imagemine._db import get_config, set_config


def _base_args(**overrides) -> SimpleNamespace:
    values = {
        "history": False,
        "config": False,
        "list_styles": False,
        "add_style": False,
        "remove_style": False,
        "launchd": None,
        "config_path": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_import_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
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

    class ImageGen:
        image_path = "generated.png"

    gemimg.GemImg = object
    gemimg.ImageGen = ImageGen

    pil = types.ModuleType("PIL")

    class ImageModule:
        class Image:
            pass

        class Resampling:
            LANCZOS = object()

    class FakePngInfo:
        def add_text(self, *_args, **_kwargs) -> None:
            return None

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


def _import_cli(monkeypatch: pytest.MonkeyPatch):
    _install_import_stubs(monkeypatch)
    _clear_imagemine_modules()
    return importlib.import_module("imagemine.cli")


class _FakeConsole:
    def __init__(self) -> None:
        self.print_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.exception_calls: list[dict[str, object]] = []

    def print(self, *args, **kwargs) -> None:
        self.print_calls.append((args, kwargs))

    def print_exception(self, **kwargs) -> None:
        self.exception_calls.append(kwargs)


def _printed_text(console: _FakeConsole) -> list[str]:
    return [str(args[0]) for args, _ in console.print_calls if args]


def _wizard_answers(*explicit_values: str) -> iter[str]:
    padded_answers = list(explicit_values)
    padded_answers.extend([""] * (len(cfg._CONFIG_FIELDS) - len(padded_answers)))
    return iter(padded_answers)


@pytest.mark.parametrize(
    ("flag_name", "handler_name"),
    [
        ("history", "_show_history"),
        ("config", "_run_config_wizard"),
        ("list_styles", "_show_styles"),
        ("add_style", "_run_add_style"),
        ("remove_style", "_run_remove_style"),
    ],
)
def test_dispatch_subcommand_routes_non_launchd_flags(
    monkeypatch: pytest.MonkeyPatch,
    flag_name: str,
    handler_name: str,
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(commands, handler_name, lambda *args: calls.append(args))

    handled = commands.dispatch_subcommand(
        _base_args(**{flag_name: True}),
        conn="db-conn",
        console="console",
        err=lambda _msg: None,
    )

    assert handled is True
    assert calls == [("db-conn", "console")] or calls == [("db-conn",)]


def test_dispatch_subcommand_launchd_with_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launchd_calls: list[tuple[object, object, object]] = []
    monkeypatch.setattr(
        commands,
        "_write_launchd_plist",
        lambda conn, config_path, interval_minutes: launchd_calls.append(
            (conn, config_path, interval_minutes),
        ),
    )

    handled = commands.dispatch_subcommand(
        _base_args(launchd=45, config_path="/tmp/imagemine.db"),
        conn="db-conn",
        console="console",
        err=lambda _msg: None,
    )

    assert handled is True
    assert launchd_calls == [("db-conn", "/tmp/imagemine.db", 45)]


def test_dispatch_subcommand_returns_false_without_matching_flag() -> None:
    handled = commands.dispatch_subcommand(
        _base_args(),
        conn="db-conn",
        console="console",
        err=lambda _msg: None,
    )

    assert handled is False


def test_style_database_helpers_round_trip(conn) -> None:
    conn.execute("DELETE FROM styles")
    conn.commit()

    assert styles.least_used_style(conn) == (None, None)

    styles.add_style(conn, "Beta", "second")
    styles.add_style(conn, "Alpha", "first")
    styles.increment_style_count(conn, "Beta")

    assert styles.least_used_style(conn) == ("Alpha", "first")
    assert styles.get_all_styles(conn) == [
        ("Alpha", "first", 0, styles.get_all_styles(conn)[0][3]),
        ("Beta", "second", 1, styles.get_all_styles(conn)[1][3]),
    ]

    styles.remove_style(conn, "Alpha")

    assert [row[0] for row in styles.get_all_styles(conn)] == ["Beta"]


def test_run_add_style_saves_trimmed_values(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["  Dreamscape  ", "  glowing clouds  "])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    styles._run_add_style(conn)

    assert conn.execute(
        "SELECT description FROM styles WHERE name = ?",
        ("Dreamscape",),
    ).fetchone() == ("glowing clouds",)
    assert any(
        "Style [magenta]Dreamscape[/] saved." in text
        for text in _printed_text(fake_console)
    )


def test_run_add_style_blank_name_exits(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "   ")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_add_style(conn)

    assert exc_info.value.code == 1
    assert any("Name is required." in text for text in _printed_text(fake_console))


def test_run_add_style_blank_description_exits(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["Neon", "   "])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    with pytest.raises(SystemExit) as exc_info:
        styles._run_add_style(conn)

    assert exc_info.value.code == 1
    assert any(
        "Description is required." in text for text in _printed_text(fake_console)
    )


def test_run_remove_style_no_styles_returns(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    conn.execute("DELETE FROM styles")
    conn.commit()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)

    styles._run_remove_style(conn)

    assert any("No styles found." in text for text in _printed_text(fake_console))


def test_run_remove_style_blank_selection_cancels(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "   ")

    styles._run_remove_style(conn)

    assert any("Cancelled." in text for text in _printed_text(fake_console))


def test_run_remove_style_invalid_selection_exits(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "x,2")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_remove_style(conn)

    assert exc_info.value.code == 1
    assert any("Invalid selection" in text for text in _printed_text(fake_console))


def test_run_remove_style_out_of_range_exits(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["999"])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    with pytest.raises(SystemExit) as exc_info:
        styles._run_remove_style(conn)

    assert exc_info.value.code == 1
    assert any("is out of range." in text for text in _printed_text(fake_console))


def test_run_remove_style_cancelled_at_confirmation(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["1", "n"])
    original_count = conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0]
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    styles._run_remove_style(conn)

    assert conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0] == original_count
    assert any("Cancelled." in text for text in _printed_text(fake_console))


def test_run_config_wizard_saves_secret_and_plain_values(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    prompt_answers = _wizard_answers("anthropic-secret", "", "Inbox")
    set_config(conn, "ANTHROPIC_API_KEY", "existing-secret")
    monkeypatch.setattr(cfg, "Console", lambda: fake_console)
    monkeypatch.setattr(
        cfg.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    cfg._run_config_wizard(conn)

    assert get_config(conn, "ANTHROPIC_API_KEY") == "anthropic-secret"
    assert get_config(conn, "INPUT_ALBUM") == "Inbox"
    assert any(
        "ANTHROPIC_API_KEY saved" in text for text in _printed_text(fake_console)
    )
    assert any("✓ saved" in text for text in _printed_text(fake_console))


def test_run_config_wizard_skips_blank_answers(
    conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_console = _FakeConsole()
    prompt_answers = _wizard_answers()
    set_config(conn, "INPUT_ALBUM", "ExistingAlbum")
    monkeypatch.setattr(cfg, "Console", lambda: fake_console)
    monkeypatch.setattr(
        cfg.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    cfg._run_config_wizard(conn)

    assert get_config(conn, "INPUT_ALBUM") == "ExistingAlbum"
    assert any("done" in text.lower() for text in _printed_text(fake_console))


def test_cli_main_stops_after_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cli = _import_cli(monkeypatch)
    fake_console = _FakeConsole()
    args = SimpleNamespace(
        silent=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
    )
    init_db_calls: list[pathlib.Path] = []
    pipeline_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(cli, "Console", lambda **_kwargs: fake_console)
    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(
        cli,
        "init_db",
        lambda db_path: init_db_calls.append(db_path) or "db",
    )
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: True)
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *_args, **_kwargs: pipeline_calls.append((_args, _kwargs)),
    )

    cli.main()

    assert init_db_calls == [cli.DEFAULT_DB_PATH]
    assert pipeline_calls == []
    assert (tmp_path / "out").exists()


def test_cli_main_runs_pipeline_with_resolved_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cli = _import_cli(monkeypatch)
    fake_console = _FakeConsole()
    args = SimpleNamespace(
        silent=True,
        session_svg=True,
        output_dir=str(tmp_path / "renders"),
        config_path="~/imagemine.db",
        image_path="photo.jpg",
        input_album="cli-album",
        destination_album="cli-destination",
        desc_temp=0.4,
        img_temp=0.9,
        story="story",
        style="custom style",
        fresh=True,
        aspect_ratio="16:9",
    )
    pipeline_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    required_calls: list[tuple[str, str | None, object]] = []
    option_calls: list[tuple[str, object, str | None]] = []

    monkeypatch.setattr(cli, "Console", lambda **_kwargs: fake_console)
    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "time", SimpleNamespace(monotonic=lambda: 123.45))
    monkeypatch.setattr(cli, "init_db", lambda db_path: ("db", db_path))
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)

    def fake_resolve_required_option(
        conn,
        cli_value,
        config_key,
        *,
        env_key=None,
        default,
        cast=None,
    ):
        required_calls.append((config_key, env_key, default))
        return {
            "DEFAULT_DESC_TEMP": 1.2,
            "DEFAULT_IMG_TEMP": 0.8,
            "CLAUDE_MODEL": "claude-override",
            "GEMINI_MODEL": "gemini-override",
        }[config_key]

    def fake_resolve_option(conn, cli_value, config_key, *, env_key=None, cast=None):
        option_calls.append((config_key, cli_value, env_key))
        return f"resolved-{config_key.lower()}"

    monkeypatch.setattr(cli, "_resolve_required_option", fake_resolve_required_option)
    monkeypatch.setattr(cli, "_resolve_option", fake_resolve_option)
    monkeypatch.setattr(
        cli,
        "_resolve_api_key",
        lambda _conn, key, _prompt: f"{key.lower()}-value",
    )
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda *args_, **kwargs: pipeline_calls.append((args_, kwargs)),
    )

    cli.main()

    assert required_calls == [
        ("DEFAULT_DESC_TEMP", None, 1.0),
        ("DEFAULT_IMG_TEMP", None, 1.0),
        ("CLAUDE_MODEL", "CLAUDE_MODEL", cli.DEFAULT_DESCRIPTION_MODEL),
        ("GEMINI_MODEL", "GEMINI_MODEL", cli.DEFAULT_IMAGE_MODEL),
    ]
    assert option_calls == [
        ("INPUT_ALBUM", "cli-album", "INPUT_ALBUM"),
        ("DESTINATION_ALBUM", "cli-destination", "DESTINATION_ALBUM"),
        ("DESCRIPTION_PROMPT_SUFFIX", None, "DESCRIPTION_PROMPT_SUFFIX"),
        ("GENERATION_PROMPT_SUFFIX", None, "GENERATION_PROMPT_SUFFIX"),
        ("ASPECT_RATIO", "16:9", "ASPECT_RATIO"),
    ]
    pipeline_args, pipeline_kwargs = pipeline_calls[0]
    assert pipeline_args[:4] == (
        ("db", pathlib.Path("~/imagemine.db").expanduser()),
        fake_console,
        pipeline_args[2],
        123.45,
    )
    assert pipeline_args[4] == (tmp_path / "renders").resolve()
    assert pipeline_kwargs == {
        "image_path": "photo.jpg",
        "input_album": "resolved-input_album",
        "destination_album": "resolved-destination_album",
        "desc_temp": 1.2,
        "img_temp": 0.8,
        "claude_model": "claude-override",
        "gemini_model": "gemini-override",
        "anthropic_api_key": "anthropic_api_key-value",
        "gemini_api_key": "gemini_api_key-value",
        "story": "story",
        "style": "custom style",
        "fresh": True,
        "session_svg": True,
        "desc_prompt_suffix": "resolved-description_prompt_suffix",
        "gen_prompt_suffix": "resolved-generation_prompt_suffix",
        "aspect_ratio": "resolved-aspect_ratio",
    }


def test_cli_main_err_prints_exception_when_called_during_handled_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cli = _import_cli(monkeypatch)
    fake_console = _FakeConsole()
    args = SimpleNamespace(
        silent=False,
        session_svg=False,
        output_dir=str(tmp_path / "out"),
        config_path=None,
        image_path=None,
        input_album=None,
        destination_album=None,
        desc_temp=None,
        img_temp=None,
        story=None,
        style=None,
        fresh=False,
        aspect_ratio=None,
    )

    monkeypatch.setattr(cli, "Console", lambda **_kwargs: fake_console)
    monkeypatch.setattr(cli, "_parse_args", lambda: args)
    monkeypatch.setattr(cli, "time", SimpleNamespace(monotonic=lambda: 9.87))
    monkeypatch.setattr(cli, "init_db", lambda db_path: ("db", db_path))
    monkeypatch.setattr(cli, "dispatch_subcommand", lambda *_args: False)
    monkeypatch.setattr(
        cli,
        "_resolve_required_option",
        lambda *_args, **_kwargs: 1.0,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_option",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_resolve_api_key",
        lambda *_args, **_kwargs: "key",
    )

    def fake_run_pipeline(_conn, _console, err, *_args, **_kwargs) -> None:
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            err("pipeline failed")

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    cli.main()

    assert fake_console.exception_calls == [{"show_locals": False}]
    assert any("pipeline failed" in text for text in _printed_text(fake_console))
