"""Tests for the --choose-style interactive style picker."""

import pytest

import imagemine._styles as styles


class _FakeConsole:
    def __init__(self) -> None:
        self.print_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def print(self, *args, **kwargs) -> None:
        self.print_calls.append((args, kwargs))


def _printed_text(console: _FakeConsole) -> list[str]:
    return [str(args[0]) for args, _ in console.print_calls if args]


def _selected_styles(
    conn,
    indices: tuple[int, ...],
) -> list[tuple[str, str]]:
    all_styles = styles.get_all_styles(conn)
    return [(all_styles[idx - 1][0], all_styles[idx - 1][1]) for idx in indices]


def test_choose_single_style(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["1"])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    result = styles._run_choose_style(conn)
    expected_name, expected_desc = _selected_styles(conn, (1,))[0]

    assert result.style_names == (expected_name,)
    assert result.style_prompt == f"{expected_name}: {expected_desc}"
    assert any("Selected" in text for text in _printed_text(fake_console))


def test_choose_multiple_styles_blends(conn, monkeypatch) -> None:
    fake_console = _FakeConsole()
    prompt_answers = iter(["1,2,3"])
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )

    result = styles._run_choose_style(conn)
    expected_candidates = _selected_styles(conn, (1, 2, 3))

    assert result.style_names == tuple(name for name, _ in expected_candidates)
    assert result.style_prompt == "; ".join(
        f"{name}: {desc}" for name, desc in expected_candidates
    )
    assert any("Blending" in text for text in _printed_text(fake_console))


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


def test_choose_style_separator_only_input_warns_and_exits(
    conn,
    monkeypatch,
) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: " , , ")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_choose_style(conn)

    assert exc_info.value.code == 1
    assert any(
        "Enter at least one style number." in text
        for text in _printed_text(fake_console)
    )


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

    result = styles._run_choose_style(conn)
    expected_name, expected_desc = _selected_styles(conn, (1,))[0]

    assert result.style_names == (expected_name,)
    assert result.style_prompt == f"{expected_name}: {expected_desc}"


def test_run_remove_style_separator_only_input_warns_and_exits(
    conn,
    monkeypatch,
) -> None:
    fake_console = _FakeConsole()
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(styles.Prompt, "ask", lambda *_args, **_kwargs: ",,,")

    with pytest.raises(SystemExit) as exc_info:
        styles._run_remove_style(conn)

    assert exc_info.value.code == 1
    assert any(
        "Enter at least one style number." in text
        for text in _printed_text(fake_console)
    )
