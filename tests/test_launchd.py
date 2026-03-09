import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import imagemine._launchd as lm
from imagemine._launchd import _write_launchd_plist


def _patch_plist_path(monkeypatch, tmp_path) -> pathlib.Path:
    fake_path = tmp_path / "imagemine.plist"
    monkeypatch.setattr(lm, "_PLIST_PATH", fake_path)
    return fake_path


def _silent_console(monkeypatch) -> None:
    """Replace Console so nothing is printed during tests."""
    import types

    fake = types.SimpleNamespace(print=lambda *a, **kw: None)
    monkeypatch.setattr(lm, "Console", lambda: fake)


# ---------------------------------------------------------------------------
# binary resolution
# ---------------------------------------------------------------------------


def test_uses_imagemine_binary_when_found(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(
        lm.shutil, "which", lambda name: "/usr/local/bin/imagemine" if name == "imagemine" else None
    )

    _write_launchd_plist(interval_minutes=30)

    content = plist_path.read_text()
    assert "/usr/local/bin/imagemine" in content
    assert "uvx" not in content


def test_falls_back_to_uvx_when_imagemine_not_found(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(
        lm.shutil, "which", lambda name: "/usr/local/bin/uvx" if name == "uvx" else None
    )

    _write_launchd_plist(interval_minutes=30)

    content = plist_path.read_text()
    assert "/usr/local/bin/uvx" in content
    assert "<string>imagemine</string>" in content


def test_falls_back_to_bare_uvx_when_uvx_not_in_path(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=30)

    content = plist_path.read_text()
    assert "<string>uvx</string>" in content


# ---------------------------------------------------------------------------
# StartInterval
# ---------------------------------------------------------------------------


def test_start_interval_is_minutes_times_60(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=45)

    assert "<integer>2700</integer>" in plist_path.read_text()


def test_start_interval_one_minute(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=1)

    assert "<integer>60</integer>" in plist_path.read_text()


# ---------------------------------------------------------------------------
# config_path
# ---------------------------------------------------------------------------


def test_config_path_appended_to_args(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(config_path="/home/user/work.db", interval_minutes=30)

    content = plist_path.read_text()
    assert "<string>--config-path</string>" in content
    assert "<string>/home/user/work.db</string>" in content


def test_no_config_path_not_in_plist(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=30)

    assert "--config-path" not in plist_path.read_text()


# ---------------------------------------------------------------------------
# interactive prompt
# ---------------------------------------------------------------------------


def test_prompts_for_interval_when_none(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)
    monkeypatch.setattr(lm.IntPrompt, "ask", lambda *a, **kw: 20)

    _write_launchd_plist(interval_minutes=None)

    assert "<integer>1200</integer>" in plist_path.read_text()


def test_zero_interval_from_prompt_exits(monkeypatch, tmp_path) -> None:
    _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)
    monkeypatch.setattr(lm.IntPrompt, "ask", lambda *a, **kw: 0)

    with pytest.raises(SystemExit) as exc_info:
        _write_launchd_plist(interval_minutes=None)

    assert exc_info.value.code == 1


def test_negative_interval_from_prompt_exits(monkeypatch, tmp_path) -> None:
    _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)
    monkeypatch.setattr(lm.IntPrompt, "ask", lambda *a, **kw: -5)

    with pytest.raises(SystemExit) as exc_info:
        _write_launchd_plist(interval_minutes=None)

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# plist structure
# ---------------------------------------------------------------------------


def test_plist_label_is_imagemine(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=30)

    content = plist_path.read_text()
    assert "<key>Label</key>" in content
    assert "<string>imagemine</string>" in content


def test_plist_run_at_load_is_true(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=30)

    assert "<true/>" in plist_path.read_text()


def test_plist_log_paths_present(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    _write_launchd_plist(interval_minutes=30)

    content = plist_path.read_text()
    assert "/tmp/imagemine.log" in content


def test_plist_file_created(monkeypatch, tmp_path) -> None:
    plist_path = _patch_plist_path(monkeypatch, tmp_path)
    _silent_console(monkeypatch)
    monkeypatch.setattr(lm.shutil, "which", lambda _: None)

    assert not plist_path.exists()
    _write_launchd_plist(interval_minutes=30)
    assert plist_path.exists()
