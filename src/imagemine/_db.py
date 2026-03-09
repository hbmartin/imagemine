import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib


def init_db(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_file_path TEXT,
            resized_file_path TEXT,
            generated_description TEXT,
            description_model_name TEXT,
            desc_temp REAL,
            output_image_path TEXT,
            image_model_name TEXT,
            img_temp REAL,
            desc_gen_ms INTEGER,
            img_gen_ms INTEGER,
            started_at TEXT,
            input_album_photo_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_config(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM config WHERE key = ?",
        (key,),
    ).fetchone()
    return row[0] if row else None


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def insert_run(conn: sqlite3.Connection, input_file_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO runs (input_file_path, started_at) VALUES (?, datetime('now'))",
        (input_file_path,),
    )
    conn.commit()
    if cur.lastrowid is None:
        msg = "INSERT did not return a row ID"
        raise RuntimeError(msg)
    return cur.lastrowid


def update_run(conn: sqlite3.Connection, run_id: int, **kwargs: str | float) -> None:
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    conn.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*kwargs.values(), run_id))
    conn.commit()


def avg_duration_ms(conn: sqlite3.Connection, column: str) -> float | None:
    row = conn.execute(
        f"SELECT AVG({column}) FROM runs WHERE {column} IS NOT NULL",
    ).fetchone()
    val = row[0] if row else None
    return float(val) if val is not None else None


def lookup_description(conn: sqlite3.Connection, input_file_path: str) -> str | None:
    row = conn.execute(
        "SELECT generated_description FROM runs "
        "WHERE input_file_path = ? AND generated_description IS NOT NULL LIMIT 1",
        (input_file_path,),
    ).fetchone()
    return row[0] if row else None
