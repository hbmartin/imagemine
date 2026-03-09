import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

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


def _mem():
    """Return an in-memory DB with the imagemine schema."""
    return init_db(":memory:")


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


def test_init_db_creates_tables() -> None:
    conn = _mem()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"runs", "styles", "config"}.issubset(tables)


def test_init_db_seeds_styles() -> None:
    conn = _mem()
    count = conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0]
    assert count > 0


def test_init_db_is_idempotent() -> None:
    conn = _mem()
    # Calling init_db a second time on the same connection should not raise.
    init_db(":memory:")


# ---------------------------------------------------------------------------
# get_config / set_config
# ---------------------------------------------------------------------------


def test_get_config_returns_none_for_missing_key() -> None:
    assert get_config(_mem(), "MISSING_KEY") is None


def test_set_and_get_config_roundtrip() -> None:
    conn = _mem()
    set_config(conn, "MY_KEY", "my_value")
    assert get_config(conn, "MY_KEY") == "my_value"


def test_set_config_overwrites_existing_value() -> None:
    conn = _mem()
    set_config(conn, "KEY", "old")
    set_config(conn, "KEY", "new")
    assert get_config(conn, "KEY") == "new"


# ---------------------------------------------------------------------------
# insert_run
# ---------------------------------------------------------------------------


def test_insert_run_returns_integer_id() -> None:
    run_id = insert_run(_mem(), "/path/to/photo.jpg")
    assert isinstance(run_id, int)
    assert run_id >= 1


def test_insert_run_ids_are_increasing() -> None:
    conn = _mem()
    id1 = insert_run(conn, "/a.jpg")
    id2 = insert_run(conn, "/b.jpg")
    assert id2 > id1


def test_insert_run_stores_input_path() -> None:
    conn = _mem()
    run_id = insert_run(conn, "/my/photo.jpg")
    row = conn.execute(
        "SELECT input_file_path FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row[0] == "/my/photo.jpg"


# ---------------------------------------------------------------------------
# update_run
# ---------------------------------------------------------------------------


def test_update_run_sets_single_field() -> None:
    conn = _mem()
    run_id = insert_run(conn, "/photo.jpg")
    update_run(conn, run_id, generated_description="lovely scene")
    row = conn.execute(
        "SELECT generated_description FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row[0] == "lovely scene"


def test_update_run_sets_multiple_fields() -> None:
    conn = _mem()
    run_id = insert_run(conn, "/photo.jpg")
    update_run(conn, run_id, generated_description="a nice photo", desc_temp=0.7)
    row = conn.execute(
        "SELECT generated_description, desc_temp FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    assert row[0] == "a nice photo"
    assert row[1] == 0.7


# ---------------------------------------------------------------------------
# lookup_description
# ---------------------------------------------------------------------------


def test_lookup_description_returns_none_when_no_run() -> None:
    assert lookup_description(_mem(), "/photo.jpg", "claude-sonnet-4-0") is None


def test_lookup_description_returns_none_when_description_not_set() -> None:
    conn = _mem()
    insert_run(conn, "/photo.jpg")
    assert lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0") is None


def test_lookup_description_finds_existing_description() -> None:
    conn = _mem()
    run_id = insert_run(conn, "/photo.jpg")
    update_run(
        conn,
        run_id,
        generated_description="lovely scene",
        description_model_name="claude-sonnet-4-0",
    )
    assert (
        lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0") == "lovely scene"
    )


def test_lookup_description_ignores_other_paths() -> None:
    conn = _mem()
    run_id = insert_run(conn, "/a.jpg")
    update_run(
        conn,
        run_id,
        generated_description="photo A",
        description_model_name="claude-sonnet-4-0",
    )
    assert lookup_description(conn, "/b.jpg", "claude-sonnet-4-0") is None


def test_lookup_description_ignores_other_models() -> None:
    conn = _mem()
    run_id = insert_run(conn, "/photo.jpg")
    update_run(
        conn,
        run_id,
        generated_description="old model output",
        description_model_name="claude-sonnet-4-0",
    )

    assert lookup_description(conn, "/photo.jpg", "claude-haiku-4-0") is None


def test_lookup_description_returns_latest_match_for_model() -> None:
    conn = _mem()
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
        generated_description="second output",
        description_model_name="claude-sonnet-4-0",
    )

    assert lookup_description(conn, "/photo.jpg", "claude-sonnet-4-0") == "second output"


# ---------------------------------------------------------------------------
# avg_duration_ms
# ---------------------------------------------------------------------------


def test_avg_duration_ms_returns_none_when_no_data() -> None:
    assert avg_duration_ms(_mem(), "desc_gen_ms") is None


def test_avg_duration_ms_computes_average() -> None:
    conn = _mem()
    id1 = insert_run(conn, "/a.jpg")
    id2 = insert_run(conn, "/b.jpg")
    update_run(conn, id1, desc_gen_ms=100)
    update_run(conn, id2, desc_gen_ms=200)
    assert avg_duration_ms(conn, "desc_gen_ms") == 150.0


def test_avg_duration_ms_ignores_null_rows() -> None:
    conn = _mem()
    id1 = insert_run(conn, "/a.jpg")
    insert_run(conn, "/b.jpg")  # no duration set
    update_run(conn, id1, desc_gen_ms=300)
    assert avg_duration_ms(conn, "desc_gen_ms") == 300.0


# ---------------------------------------------------------------------------
# random_style
# ---------------------------------------------------------------------------


def test_random_style_returns_name_and_description() -> None:
    conn = _mem()
    name, desc = random_style(conn)
    assert name is not None
    assert desc is not None
    assert isinstance(name, str)
    assert isinstance(desc, str)


def test_random_style_empty_styles_table_returns_nones() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE styles (name TEXT PRIMARY KEY, description TEXT NOT NULL)"
    )
    conn.commit()
    name, desc = random_style(conn)
    assert name is None
    assert desc is None
