from types import SimpleNamespace

import imagemine._styles as styles


def test_run_remove_style_deduplicates_selected_indices(monkeypatch) -> None:
    printed = []
    removed = []
    prompt_answers = iter(["1,1,2", "y"])

    fake_console = SimpleNamespace(print=lambda *args, **_kwargs: printed.append(args))
    monkeypatch.setattr(styles, "Console", lambda: fake_console)
    monkeypatch.setattr(
        styles,
        "get_all_styles",
        lambda _conn: [
            ("Alpha", "first", 0, "2026-03-09T00:00:00"),
            ("Beta", "second", 0, "2026-03-09T00:00:00"),
        ],
    )
    monkeypatch.setattr(
        styles.Prompt,
        "ask",
        lambda *_args, **_kwargs: next(prompt_answers),
    )
    monkeypatch.setattr(
        styles,
        "remove_style",
        lambda _conn, name: removed.append(name),
    )

    styles._run_remove_style(object())

    assert removed == ["Alpha", "Beta"]
    assert ("\n  [green]✓[/] Removed 2 style(s).",) in printed
