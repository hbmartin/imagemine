"""Tests for _character_mapping interactive functions."""

import pytest
from rich.console import Console

import imagemine._character_mapping as cm
from imagemine._db import add_character_mapping, get_all_character_mappings, init_db


@pytest.fixture
def conn():
    c = init_db(":memory:")
    yield c
    c.close()


# ---------------------------------------------------------------------------
# _run_add_character_mapping
# ---------------------------------------------------------------------------


def test_run_add_character_mapping_saves(conn, monkeypatch) -> None:
    inputs = iter(["Bob", "Robert"])
    monkeypatch.setattr(
        "rich.prompt.Prompt.ask",
        lambda *_args, **_kwargs: next(inputs),
    )

    cm._run_add_character_mapping(conn)

    assert get_all_character_mappings(conn) == [("Bob", "Robert")]


def test_run_add_character_mapping_empty_input_exits(conn, monkeypatch) -> None:
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *_args, **_kwargs: "  ")

    with pytest.raises(SystemExit) as exc_info:
        cm._run_add_character_mapping(conn)

    assert exc_info.value.code == 1


def test_run_add_character_mapping_empty_mapped_exits(conn, monkeypatch) -> None:
    inputs = iter(["Bob", "  "])
    monkeypatch.setattr(
        "rich.prompt.Prompt.ask",
        lambda *_args, **_kwargs: next(inputs),
    )

    with pytest.raises(SystemExit) as exc_info:
        cm._run_add_character_mapping(conn)

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# _print_numbered_mappings
# ---------------------------------------------------------------------------


def test_print_numbered_mappings() -> None:
    console = Console(record=True)
    mappings = [("Alice", "Alicia"), ("Bob", "Robert")]

    cm._print_numbered_mappings(console, mappings)

    rendered = console.export_text()
    assert "Alice" in rendered
    assert "Alicia" in rendered
    assert "Bob" in rendered
    assert "Robert" in rendered
    assert "1" in rendered
    assert "2" in rendered


# ---------------------------------------------------------------------------
# _run_remove_character_mapping
# ---------------------------------------------------------------------------


def test_run_remove_no_mappings(conn, monkeypatch) -> None:
    console = Console(record=True)
    monkeypatch.setattr(cm, "Console", lambda: console)

    cm._run_remove_character_mapping(conn)

    assert "No character mappings found." in console.export_text()


def test_run_remove_cancelled_empty_input(conn, monkeypatch) -> None:
    add_character_mapping(conn, "Bob", "Robert")
    console = Console(record=True)
    monkeypatch.setattr(cm, "Console", lambda: console)
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *_args, **_kwargs: "")

    cm._run_remove_character_mapping(conn)

    assert "Cancelled." in console.export_text()
    assert get_all_character_mappings(conn) == [("Bob", "Robert")]


def test_run_remove_cancelled_on_confirm(conn, monkeypatch) -> None:
    add_character_mapping(conn, "Bob", "Robert")
    console = Console(record=True)
    monkeypatch.setattr(cm, "Console", lambda: console)
    responses = iter(["1", "n"])
    monkeypatch.setattr(
        "rich.prompt.Prompt.ask",
        lambda *_args, **_kwargs: next(responses),
    )

    cm._run_remove_character_mapping(conn)

    assert "Cancelled." in console.export_text()
    assert get_all_character_mappings(conn) == [("Bob", "Robert")]


def test_run_remove_confirmed(conn, monkeypatch) -> None:
    add_character_mapping(conn, "Alice", "Alicia")
    add_character_mapping(conn, "Bob", "Robert")
    console = Console(record=True)
    monkeypatch.setattr(cm, "Console", lambda: console)
    responses = iter(["1", "y"])
    monkeypatch.setattr(
        "rich.prompt.Prompt.ask",
        lambda *_args, **_kwargs: next(responses),
    )

    cm._run_remove_character_mapping(conn)

    rendered = console.export_text()
    assert "Removed 1 mapping(s)" in rendered
    assert get_all_character_mappings(conn) == [("Bob", "Robert")]


def test_run_remove_separator_only_input_mentions_mapping(
    conn,
    monkeypatch,
) -> None:
    add_character_mapping(conn, "Alice", "Alicia")
    console = Console(record=True)
    monkeypatch.setattr(cm, "Console", lambda: console)
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *_args, **_kwargs: ",,,")

    with pytest.raises(SystemExit) as exc_info:
        cm._run_remove_character_mapping(conn)

    assert exc_info.value.code == 1
    rendered = console.export_text()
    assert "Enter at least one mapping number." in rendered
    assert "style number" not in rendered
