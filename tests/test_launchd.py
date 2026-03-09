import pathlib
import sys
import types

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import imagemine._launchd as lm
from imagemine._launchd import _write_launchd_plist


def _patch_plist_path(monkeypatch, tmp_path) -> pathlib.Path:
    fake_path = tmp_path / "imagemine.plist"
    monkeypatch.setattr(lm, "_PLIST_PATH", fake_path)
    return fake_path


def _silent_console(monkeypatch) -> None:
    fake = types.SimpleNamespace(print=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(lm, "Console", lambda: fake)


def test_requires_uvx_on_path(launchd_conn, monkeypatch, tmp_path) -> None:
    _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    with pytest.raises(SystemExit) as exc_info:
        _write_launchd_plist(launchd_conn, interval_minutes=30)

    assert exc_info.value.code == 1


def test_start_interval_is_minutes_times_60(launchd_conn, monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _name: "/usr/local/bin/uvx")

    _write_launchd_plist(launchd_conn, interval_minutes=45)

    content = plist_path.read_text()
    assert "/usr/local/bin/uvx" in content
    assert "<string>imagemine</string>" in content
    assert "<integer>2700</integer>" in content


def test_config_path_is_escaped_in_plist(launchd_conn, monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _name: "/usr/local/bin/uvx")

    _write_launchd_plist(
        launchd_conn,
        config_path="/home/user/<work>&db",
        interval_minutes=30,
    )

    content = plist_path.read_text()
    assert "<string>--config-path</string>" in content
    assert "<string>/home/user/&lt;work&gt;&amp;db</string>" in content
    assert "/home/user/<work>&db" not in content


def test_no_config_path_not_in_plist(launchd_conn, monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _name: "/usr/local/bin/uvx")

    _write_launchd_plist(launchd_conn, interval_minutes=30)

    assert "--config-path" not in plist_path.read_text()


def test_prompts_for_interval_when_none(launchd_conn, monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _name: "/usr/local/bin/uvx")
    monkeypatch.setattr(lm.IntPrompt, "ask", lambda *_args, **_kwargs: 20)

    _write_launchd_plist(launchd_conn, interval_minutes=None)

    assert "<integer>1200</integer>" in plist_path.read_text()


def test_zero_interval_from_prompt_exits(launchd_conn, monkeypatch, tmp_path) -> None:
    _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _name: "/usr/local/bin/uvx")
    monkeypatch.setattr(lm.IntPrompt, "ask", lambda *_args, **_kwargs: 0)

    with pytest.raises(SystemExit) as exc_info:
        _write_launchd_plist(launchd_conn, interval_minutes=None)

    assert exc_info.value.code == 1


def test_missing_required_keys_exits(conn, monkeypatch, tmp_path) -> None:
    _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _name: "/usr/local/bin/uvx")

    with pytest.raises(SystemExit) as exc_info:
        _write_launchd_plist(conn, interval_minutes=30)

    assert exc_info.value.code == 1
