import argparse
import pathlib
import sqlite3
import sys
import tempfile

import anthropic
from gemimg import GemImg
from PIL import Image

DESCRIPTION_MODEL = "claude-sonnet-4-6"
IMAGE_MODEL = "gemini-3-pro-image-preview"
DB_PATH = pathlib.Path("imagemine.db")


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
        "INSERT INTO runs (input_file_path) VALUES (?)", (input_file_path,)
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def lookup_description(conn: sqlite3.Connection, input_file_path: str) -> str | None:
    row = conn.execute(
        "SELECT generated_description FROM runs WHERE input_file_path = ? AND generated_description IS NOT NULL LIMIT 1",
        (input_file_path,),
    ).fetchone()
    return row[0] if row else None


def update_run(conn: sqlite3.Connection, run_id: int, **kwargs) -> None:
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    conn.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*kwargs.values(), run_id))
    conn.commit()


def resize_image(path: str, output_dir: pathlib.Path, max_size=1024) -> tuple[Image.Image, pathlib.Path]:
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
                }
            ],
            betas=["files-api-2025-04-14"],
        )
    finally:
        client.beta.files.delete(uploaded.id, betas=["files-api-2025-04-14"])

    return response.content[0].text


def generate_image(description: str, image: Image.Image):
    g = GemImg(model=IMAGE_MODEL)
    return g.generate(description, image)


def main():
    parser = argparse.ArgumentParser(description="Transform a photo into a fantasy image")
    parser.add_argument("image_path", help="Path to input image")
    parser.add_argument("--output-dir", default=".", help="Output directory (default: cwd)")
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = init_db(DB_PATH)
    run_id = insert_run(conn, str(pathlib.Path(args.image_path).resolve()))

    print("Resizing image...", file=sys.stderr)
    image, resized_path = resize_image(args.image_path, output_dir)
    update_run(conn, run_id, resized_file_path=str(resized_path))

    cached = lookup_description(conn, str(pathlib.Path(args.image_path).resolve()))
    if cached:
        print("Reusing cached description from previous run.", file=sys.stderr)
        description = cached
    else:
        print("Generating fantastical description with Claude...", file=sys.stderr)
        description = describe_image(image)
        update_run(conn, run_id, generated_description=description, description_model_name=DESCRIPTION_MODEL)
    print(f"\nDescription:\n{description}\n", file=sys.stderr)

    print("Generating fantasy image with Gemini...", file=sys.stderr)
    result = generate_image(description, image)

    if result is not None:
        output_path = str(pathlib.Path(result.path).resolve()) if hasattr(result, "path") else str(result)
        update_run(conn, run_id, output_image_path=output_path, image_model_name=IMAGE_MODEL)
        print(output_path)
    else:
        print("Image generation failed.", file=sys.stderr)


if __name__ == "__main__":
    main()
