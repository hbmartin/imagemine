"""Tests for the --choose-style interactive style picker."""

from types import SimpleNamespace

import pytest

import imagemine._styles as styles


class _FakeConsole:
    def __init__(self) -> None:
        self.print_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def print(self, *args, **kwargs) -> None:
        self.print_calls.append((args, kwargs))


def _printed_text(console: _FakeConsole) -> list[str]:
    return [str(args[0]) for args, _ in console.print_calls if args]


def test_choose_single_style(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["1"])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt, "ask", lambda *_args, **_kwargs: next(prompt_answers),
    )

    name, desc = styles._run_choose_style(conn)

    assert isinstance(name, str)
    assert isinstance(desc, str)
    assert any("Selected" in text for text in _printed_text(fake_console))


def test_choose_multiple_styles_picks_one(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["1,2,3"])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt, "ask", lambda *_args, **_kwargs: next(prompt_answers),
    )

    name, desc = styles._run_choose_style(conn)

    assert isinstance(name, str)
    assert isinstance(desc, str)


def test_choose_style_empty_db_exits(conn, monkeypatch) -> None:
    conn.execute("DELETE FROM styles")
    conn.commit()
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)

    with pytest.raises(SystemExit) as exc_info:
        styles._run_choose_style(conn)

    assert exc_info.value.code == 1
    assert any("No styles found" in text for text in _printed_text(fake_console))


def test_choose_style_blank_input_exits(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "  ")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_choose_style(conn)

    assert exc_info.value.code == 0


def test_choose_style_invalid_input_exits(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "x,y")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_choose_style(conn)

    assert exc_info.value.code == 1
    assert any("Invalid selection" in text for text in _printed_text(fake_console))


def test_choose_style_out_of_range_exits(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "999")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_choose_style(conn)

    assert exc_info.value.code == 1
    assert any("out of range" in text for text in _printed_text(fake_console))


def test_choose_style_deduplicates_indices(conn, monkeypatch) -> None:
    """Selecting '1,1' should only produce one candidate, not two."""
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: "1,1")

    name, desc = styles._run_choose_style(conn)

    assert isinstance(name, str)
    assert isinstance(desc, str)
