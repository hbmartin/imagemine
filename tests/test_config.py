import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import imagemine._config as cfg
from imagemine._config import (
    _parse_args,
    _resolve_api_key,
    _resolve_option,
    _resolve_required_option,
)
from imagemine._db import get_config, init_db, set_config

DB_TEMP = 1.5
ENV_TEMP = 0.8
CLI_TEMP = 0.5
LAUNCHD_INTERVAL = 45
CONFIG_INTERVAL = 30
CONFIG_DB_PATH = "/path/to/test.db"


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
    set_config(conn, "TEMP", str(DB_TEMP))

    result = _resolve_option(conn, None, "TEMP", cast=float)

    assert result == DB_TEMP
    assert isinstance(result, float)


def test_cast_applied_to_env_value(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.setenv("MY_TEMP", str(ENV_TEMP))

    result = _resolve_option(conn, None, "MISSING_KEY", env_key="MY_TEMP", cast=float)

    assert result == ENV_TEMP
    assert isinstance(result, float)


def test_cli_float_value_returned_unchanged() -> None:
    result = _resolve_option(_mem(), CLI_TEMP, "MISSING_KEY", cast=float)
    assert result == CLI_TEMP


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
        default=DB_TEMP,
        cast=float,
    )

    assert result == DB_TEMP
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
    conn = _mem()
    monkeypatch.delenv("MY_API_KEY", raising=False)
    fake_console = types.SimpleNamespace(print=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cfg, "Console", lambda: fake_console)
    monkeypatch.setattr(cfg.Prompt, "ask", lambda *_args, **_kwargs: "prompted-key")

    result = _resolve_api_key(conn, "MY_API_KEY", "Enter key")

    assert result == "prompted-key"
    assert get_config(conn, "MY_API_KEY") == "prompted-key"


def test_api_key_blank_prompt_exits(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.delenv("MY_API_KEY", raising=False)
    fake_console = types.SimpleNamespace(print=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cfg, "Console", lambda: fake_console)
    monkeypatch.setattr(cfg.Prompt, "ask", lambda *_args, **_kwargs: "")

    with pytest.raises(SystemExit) as exc_info:
        _resolve_api_key(conn, "MY_API_KEY", "Enter key")
    assert exc_info.value.code == 1


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
    monkeypatch.setattr(sys, "argv", ["imagemine", "--launchd", str(LAUNCHD_INTERVAL)])
    args = _parse_args()
    assert args.launchd == LAUNCHD_INTERVAL


def test_parse_args_launchd_with_config_path(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "imagemine",
            "--launchd",
            str(CONFIG_INTERVAL),
            "--config-path",
            CONFIG_DB_PATH,
        ],
    )
    args = _parse_args()
    assert args.launchd == CONFIG_INTERVAL
    assert args.config_path == CONFIG_DB_PATH


def test_parse_args_image_path_parsed(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["imagemine", "sunset.jpg"])
    args = _parse_args()
    assert args.image_path == "sunset.jpg"
    assert args.launchd is None
