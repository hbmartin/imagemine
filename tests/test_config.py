import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from imagemine._config import _resolve_option
from imagemine._db import init_db, set_config


def _mem():
    return init_db(":memory:")


# ---------------------------------------------------------------------------
# _resolve_option priority: CLI → DB → env → default
# ---------------------------------------------------------------------------


def test_cli_value_takes_priority_over_all(monkeypatch) -> None:
    conn = _mem()
    set_config(conn, "MY_KEY", "db_value")
    monkeypatch.setenv("MY_ENV", "env_value")

    result = _resolve_option(
        conn, "cli_value", "MY_KEY", env_key="MY_ENV", default="default_val"
    )

    assert result == "cli_value"


def test_db_value_used_when_cli_is_none(monkeypatch) -> None:
    conn = _mem()
    set_config(conn, "MY_KEY", "db_value")
    monkeypatch.delenv("MY_ENV", raising=False)

    result = _resolve_option(
        conn, None, "MY_KEY", env_key="MY_ENV", default="default_val"
    )

    assert result == "db_value"


def test_env_used_when_cli_and_db_are_absent(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.setenv("MY_ENV", "env_value")

    result = _resolve_option(
        conn, None, "MISSING_KEY", env_key="MY_ENV", default="default_val"
    )

    assert result == "env_value"


def test_default_used_when_nothing_else_present(monkeypatch) -> None:
    conn = _mem()
    monkeypatch.delenv("MY_ENV", raising=False)

    result = _resolve_option(
        conn, None, "MISSING_KEY", env_key="MY_ENV", default="default_val"
    )

    assert result == "default_val"


def test_returns_none_when_no_default_and_nothing_set() -> None:
    result = _resolve_option(_mem(), None, "MISSING_KEY")
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
