import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from imagemine._config import (
    _parse_args,
    _resolve_api_key,
    _resolve_option,
    _resolve_required_option,
)
from imagemine._db import get_config, init_db, set_config


def _mem():
    return init_db(":memory:")


# ---------------------------------------------------------------------------
# _resolve_option priority: CLI → DB → env
# ---------------------------------------------------------------------------


def test_cli_value_takes_priority_over_all(monkeypatch) -> None:
    conn = _mem()
    set_config(conn, "MY_KEY", "db_value")
    monkeypatch.setenv("MY_ENV", "env_value")

    result = _resolve_option(conn, "cli_value", "MY_KEY", env_key="MY_ENV")

    assert result == "cli_value"


def test_db_value_used_when_cli_is_none(monkeypatch) -> None:
    conn = _mem()
    set_config(conn, "MY_KEY", "db_value")
    monkeypatch.delenv("MY_ENV", raising=False)

    result = _resolve_option(conn, None, "MY_KEY", env_key="MY_ENV")

    assert result == "db_value"


def test_env_used_when_cli_and_db_are_absent(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.setenv("MY_ENV", "env_value")

    result = _resolve_option(conn, None, "MISSING_KEY", env_key="MY_ENV")

    assert result == "env_value"


def test_returns_none_when_nothing_set(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.delenv("MY_ENV", raising=False)

    result = _resolve_option(conn, None, "MISSING_KEY", env_key="MY_ENV")
    assert result is None


def test_cast_applied_to_db_string_value() -> None:
    conn = _mem()
    set_config(conn, "TEMP", "1.5")

    result = _resolve_option(conn, None, "TEMP", cast=float)

    assert result == 1.5
    assert isinstance(result, float)


def test_cast_applied_to_env_value(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.setenv("MY_TEMP", "0.8")

    result = _resolve_option(conn, None, "MISSING_KEY", env_key="MY_TEMP", cast=float)

    assert result == 0.8
    assert isinstance(result, float)


def test_cli_float_value_returned_unchanged() -> None:
    result = _resolve_option(_mem(), 0.5, "MISSING_KEY", cast=float)
    assert result == 0.5


# ---------------------------------------------------------------------------
# _resolve_required_option priority: CLI → DB → env → default
# ---------------------------------------------------------------------------


def test_required_default_used_when_nothing_else_present(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.delenv("MY_ENV", raising=False)

    result = _resolve_required_option(
        conn,
        None,
        "MISSING_KEY",
        env_key="MY_ENV",
        default="default_val",
    )

    assert result == "default_val"


def test_required_option_returns_default_typed_value(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.delenv("MY_TEMP", raising=False)

    result = _resolve_required_option(
        conn,
        None,
        "MISSING_KEY",
        env_key="MY_TEMP",
        default=1.5,
        cast=float,
    )

    assert result == 1.5
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# _resolve_api_key priority: DB → env → interactive prompt
# ---------------------------------------------------------------------------


def test_api_key_returned_from_db(monkeypatch) -> None:
    conn = _mem()
    set_config(conn, "ANTHROPIC_API_KEY", "db-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = _resolve_api_key(conn, "ANTHROPIC_API_KEY", "Enter key")

    assert result == "db-key"


def test_api_key_returned_from_env_when_db_empty(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.setenv("MY_API_KEY", "env-key")

    result = _resolve_api_key(conn, "MY_API_KEY", "Enter key")

    assert result == "env-key"


def test_api_key_prompt_used_when_db_and_env_absent(monkeypatch) -> None:
    import imagemine._config as cfg
    import types

    conn = _mem()
    monkeypatch.delenv("MY_API_KEY", raising=False)
    fake_console = types.SimpleNamespace(print=lambda *a, **kw: None)
    monkeypatch.setattr(cfg, "Console", lambda: fake_console)
    monkeypatch.setattr(cfg.Prompt, "ask", lambda *a, **kw: "prompted-key")

    result = _resolve_api_key(conn, "MY_API_KEY", "Enter key")

    assert result == "prompted-key"
    assert get_config(conn, "MY_API_KEY") == "prompted-key"


def test_api_key_blank_prompt_exits(monkeypatch) -> None:
    import imagemine._config as cfg
    import types

    conn = _mem()
    monkeypatch.delenv("MY_API_KEY", raising=False)
    fake_console = types.SimpleNamespace(print=lambda *a, **kw: None)
    monkeypatch.setattr(cfg, "Console", lambda: fake_console)
    monkeypatch.setattr(cfg.Prompt, "ask", lambda *a, **kw: "")

    try:
        _resolve_api_key(conn, "MY_API_KEY", "Enter key")
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")


# ---------------------------------------------------------------------------
# _parse_args — --launchd flag
# ---------------------------------------------------------------------------


def test_parse_args_launchd_absent_gives_none(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["imagemine", "photo.jpg"])
    args = _parse_args()
    assert args.launchd is None


def test_parse_args_launchd_bare_gives_zero(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["imagemine", "--launchd"])
    args = _parse_args()
    assert args.launchd == 0


def test_parse_args_launchd_with_value(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["imagemine", "--launchd", "45"])
    args = _parse_args()
    assert args.launchd == 45


def test_parse_args_launchd_with_config_path(monkeypatch) -> None:
    monkeypatch.setattr(
        sys, "argv", ["imagemine", "--launchd", "30", "--config-path", "/tmp/test.db"]
    )
    args = _parse_args()
    assert args.launchd == 30
    assert args.config_path == "/tmp/test.db"


def test_parse_args_image_path_parsed(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["imagemine", "sunset.jpg"])
    args = _parse_args()
    assert args.image_path == "sunset.jpg"
    assert args.launchd is None
