import pathlib
import sqlite3

from imagemine._db import (
    avg_duration_ms,
    get_config,
    init_db,
    insert_run,
    lookup_description,
    set_config,
    update_run,
)
from imagemine._styles import random_style

# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


def test_init_db_creates_tables(conn) -> None:
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        ).fetchall()
    }
    assert {"runs", "styles", "config"}.issubset(tables)


def test_init_db_seeds_styles(conn) -> None:
    count = conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0]
    assert count > 0


def test_init_db_is_idempotent(tmp_path: pathlib.Path) -> None:
    # Calling init_db a second time on the same path should not raise.
    db_path = tmp_path / "test.db"
    conn1 = init_db(db_path)
    conn1.close()

    conn2 = init_db(db_path)
    conn2.close()


# ---------------------------------------------------------------------------
# get_config / set_config
# ---------------------------------------------------------------------------


def test_get_config_returns_none_for_missing_key(conn) -> None:
    assert get_config(conn, "MISSING_KEY") is None


def test_set_and_get_config_roundtrip(conn) -> None:
    set_config(conn, "MY_KEY", "my_value")
    assert get_config(conn, "MY_KEY") == "my_value"


def test_set_config_overwrites_existing_value(conn) -> None:
    set_config(conn, "KEY", "old")
    set_config(conn, "KEY", "new")
    assert get_config(conn, "KEY") == "new"


# ---------------------------------------------------------------------------
# insert_run
# ---------------------------------------------------------------------------


def test_insert_run_returns_integer_id(conn) -> None:
    run_id = insert_run(conn, "/path/to/photo.jpg")
    assert isinstance(run_id, int)
    assert run_id >= 1


def test_insert_run_ids_are_increasing(conn) -> None:
    id1 = insert_run(conn, "/a.jpg")
    id2 = insert_run(conn, "/b.jpg")
    assert id2 > id1


def test_insert_run_stores_input_path(conn) -> None:
    run_id = insert_run(conn, "/my/photo.jpg")
    row = conn.execute(
        "SELECT input_file_path FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert row[0] == "/my/photo.jpg"


# ---------------------------------------------------------------------------
# update_run
# ---------------------------------------------------------------------------


def test_update_run_sets_single_field(conn) -> None:
    run_id = insert_run(conn, "/photo.jpg")
    update_run(conn, run_id, generated_description="lovely scene")
    row = conn.execute(
        "SELECT generated_description FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert row[0] == "lovely scene"


def test_update_run_sets_multiple_fields(conn) -> None:
    expected_temp = 0.7
    run_id = insert_run(conn, "/photo.jpg")
    update_run(
        conn,
        run_id,
        generated_description="a nice photo",
        desc_temp=expected_temp,
    )
    row = conn.execute(
        "SELECT generated_description, desc_temp FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert row[0] == "a nice photo"
    assert row[1] == expected_temp


# ---------------------------------------------------------------------------
# lookup_description
# ---------------------------------------------------------------------------


def test_lookup_description_returns_none_when_no_run(conn) -> None:
    assert lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0") is None


def test_lookup_description_returns_none_when_description_not_set(conn) -> None:
    insert_run(conn, "/photo.jpg")
    assert lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0") is None


def test_lookup_description_finds_existing_description(conn) -> None:
    run_id = insert_run(conn, "/photo.jpg")
    update_run(
        conn,
        run_id,
        generated_description="lovely scene",
        description_model_name="claude-sonnet-4-0",
    )
    assert lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0") == "lovely scene"


def test_lookup_description_ignores_other_paths(conn) -> None:
    run_id = insert_run(conn, "/a.jpg")
    update_run(
        conn,
        run_id,
        generated_description="photo A",
        description_model_name="claude-sonnet-4-0",
    )
    assert lookup_description(conn, "/b.jpg", "claude-sonnet-4-0") is None


def test_lookup_description_ignores_other_models(conn) -> None:
    run_id = insert_run(conn, "/photo.jpg")
    update_run(
        conn,
        run_id,
        generated_description="old model output",
        description_model_name="claude-sonnet-4-0",
    )

    assert lookup_description(conn, "/photo.jpg", "claude-haiku-4-0") is None


def test_lookup_description_returns_latest_match_for_model(conn) -> None:
    expected_description = "second output"
    first_run = insert_run(conn, "/photo.jpg")
    second_run = insert_run(conn, "/photo.jpg")
    update_run(
        conn,
        first_run,
        generated_description="first output",
        description_model_name="claude-sonnet-4-0",
    )
    update_run(
        conn,
        second_run,
        generated_description=expected_description,
        description_model_name="claude-sonnet-4-0",
    )

    assert (
        lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0")
        == expected_description
    )


# ---------------------------------------------------------------------------
# avg_duration_ms
# ---------------------------------------------------------------------------


def test_avg_duration_ms_returns_none_when_no_data(conn) -> None:
    assert avg_duration_ms(conn, "desc_gen_ms") is None


def test_avg_duration_ms_computes_average(conn) -> None:
    expected_average = 150.0
    id1 = insert_run(conn, "/a.jpg")
    id2 = insert_run(conn, "/b.jpg")
    update_run(conn, id1, desc_gen_ms=100)
    update_run(conn, id2, desc_gen_ms=200)
    assert avg_duration_ms(conn, "desc_gen_ms") == expected_average


def test_avg_duration_ms_ignores_null_rows(conn) -> None:
    expected_average = 300.0
    id1 = insert_run(conn, "/a.jpg")
    insert_run(conn, "/b.jpg")  # no duration set
    update_run(conn, id1, desc_gen_ms=300)
    assert avg_duration_ms(conn, "desc_gen_ms") == expected_average


# ---------------------------------------------------------------------------
# random_style
# ---------------------------------------------------------------------------


def test_random_style_returns_name_and_description(conn) -> None:
    name, desc = random_style(conn)
    assert name is not None
    assert desc is not None
    assert isinstance(name, str)
    assert isinstance(desc, str)


def test_random_style_empty_styles_table_returns_nones() -> None:
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE styles (name TEXT PRIMARY KEY, description TEXT NOT NULL)",
    )
    c.commit()
    name, desc = random_style(c)
    c.close()
    assert name is None
    assert desc is None
