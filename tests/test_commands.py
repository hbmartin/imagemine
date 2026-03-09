import pathlib
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import imagemine._commands as commands


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


def test_dispatch_subcommand_launchd_zero_prompts(monkeypatch) -> None:
    launchd_calls = []

    monkeypatch.setattr(
        commands,
        "_write_launchd_plist",
        lambda conn, config_path, interval_minutes: launchd_calls.append(
            (conn, config_path, interval_minutes),
        ),
    )

    handled = commands.dispatch_subcommand(
        _base_args(launchd=0, config_path="/Users/test/imagemine.db"),
        conn="db-conn",
        console=object(),
        err=lambda _msg: None,
    )

    assert handled is True
    assert launchd_calls == [("db-conn", "/Users/test/imagemine.db", None)]


def test_dispatch_subcommand_launchd_negative_exits() -> None:
    errors = []

    with pytest.raises(SystemExit) as exc_info:
        commands.dispatch_subcommand(
            _base_args(launchd=-1),
            conn="db-conn",
            console=object(),
            err=errors.append,
        )

    assert exc_info.value.code == 1
    assert errors == ["--launchd must be a positive integer."]
