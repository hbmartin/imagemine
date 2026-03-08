import argparse
import pathlib
import sys

from ._core import (
    DB_PATH,
    DESCRIPTION_MODEL,
    IMAGE_MODEL,
    describe_image,
    generate_image,
    init_db,
    insert_run,
    lookup_description,
    resize_image,
    update_run,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transform a photo into a fantasy image",
    )
    parser.add_argument("image_path", help="Path to input image")
    parser.add_argument(
        "--output-dir", default=".", help="Output directory (default: cwd)",
    )
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = str(pathlib.Path(args.image_path).resolve())

    conn = init_db(DB_PATH)
    run_id = insert_run(conn, input_path)

    print("Resizing image...", file=sys.stderr)
    image, resized_path = resize_image(args.image_path, output_dir)
    update_run(conn, run_id, resized_file_path=str(resized_path))

    cached = lookup_description(conn, input_path)
    if cached:
        print("Reusing cached description from previous run.", file=sys.stderr)
        description = cached
    else:
        print("Generating fantastical description with Claude...", file=sys.stderr)
        description = describe_image(image)
        update_run(
            conn,
            run_id,
            generated_description=description,
            description_model_name=DESCRIPTION_MODEL,
        )
    print(f"\nDescription:\n{description}\n", file=sys.stderr)

    print("Generating fantasy image with Gemini...", file=sys.stderr)
    result = generate_image(description, image)

    if result is not None:
        output_path = str(getattr(result, "path", result))
        update_run(
            conn, run_id, output_image_path=output_path, image_model_name=IMAGE_MODEL,
        )
        print(output_path)
    else:
        print("Image generation failed.", file=sys.stderr)
