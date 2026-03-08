import pathlib
import sqlite3
import tempfile

import anthropic
from gemimg import GemImg
from PIL import Image

DESCRIPTION_MODEL = "claude-sonnet-4-6"
IMAGE_MODEL = "gemini-3-pro-image-preview"
DB_PATH = pathlib.Path("imagemine.db")


# --- Database ---


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
        "INSERT INTO runs (input_file_path) VALUES (?)", (input_file_path,),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def update_run(conn: sqlite3.Connection, run_id: int, **kwargs) -> None:
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


# --- Pipeline ---


def resize_image(
    path: str, output_dir: pathlib.Path, max_size: int = 1024,
) -> tuple[Image.Image, pathlib.Path]:
    image = Image.open(path)
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    stem = pathlib.Path(path).stem
    resized_path = output_dir / f"{stem}_resized.jpg"
    image.save(resized_path, format="JPEG")
    return image, resized_path


def describe_image(image: Image.Image) -> str:
    client = anthropic.Anthropic()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image.save(tmp, format="JPEG")
        tmp_path = pathlib.Path(tmp.name)

    uploaded = client.beta.files.upload(
        file=tmp_path,
        betas=["files-api-2025-04-14"],
    )
    tmp_path.unlink(missing_ok=True)

    try:
        response = client.beta.messages.create(
            model=DESCRIPTION_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "file",
                                "file_id": uploaded.id,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Imagine a fantastical scenario set an hour after this photo",
                        },
                    ],
                },
            ],
            betas=["files-api-2025-04-14"],
        )
    finally:
        client.beta.files.delete(uploaded.id, betas=["files-api-2025-04-14"])

    return response.content[0].text


def generate_image(description: str, image: Image.Image):
    g = GemImg(model=IMAGE_MODEL)
    return g.generate(description, image)
