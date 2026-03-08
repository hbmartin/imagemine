import pathlib
import sqlite3


def init_db(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_file_path TEXT,
            resized_file_path TEXT,
            generated_description TEXT,
            description_model_name TEXT,
            output_image_path TEXT,
            image_model_name TEXT
        )
    """)
    conn.commit()
    return conn


def insert_run(conn: sqlite3.Connection, input_file_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO runs (input_file_path) VALUES (?)",
        (input_file_path,),
    )
    conn.commit()
    if cur.lastrowid is None:
        msg = "INSERT did not return a row ID"
        raise RuntimeError(msg)
    return cur.lastrowid


def update_run(conn: sqlite3.Connection, run_id: int, **kwargs: str) -> None:
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    conn.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*kwargs.values(), run_id))
    conn.commit()


def lookup_description(conn: sqlite3.Connection, input_file_path: str) -> str | None:
    row = conn.execute(
        "SELECT generated_description FROM runs "
        "WHERE input_file_path = ? AND generated_description IS NOT NULL LIMIT 1",
        (input_file_path,),
    ).fetchone()
    return row[0] if row else None
