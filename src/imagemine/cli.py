"""Command-line interface for imagemine."""

import argparse
import pathlib
import sys

from ._core import DB_PATH, DESCRIPTION_MODEL, IMAGE_MODEL, resize_image
from ._db import init_db, insert_run, lookup_description, update_run
from ._describe import describe_image
from ._generate import generate_image


def main() -> None:
    """Run the imagemine pipeline: resize, describe, generate."""
    parser = argparse.ArgumentParser(
        description="Transform a photo into a fantasy image",
    )
    parser.add_argument("image_path", help="Path to input image")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory (default: cwd)",
    )
    parser.add_argument(
        "--desc-temp",
        type=float,
        default=1.0,
        help="Sampling temperature for description generation (default: 1.0)",
    )
    parser.add_argument(
        "--img-temp",
        type=float,
        default=1.0,
        help="Sampling temperature for image generation (default: 1.0)",
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
        description = describe_image(image, temperature=args.desc_temp)
        update_run(
            conn,
            run_id,
            generated_description=description,
            description_model_name=DESCRIPTION_MODEL,
            desc_temp=args.desc_temp,
        )
    print(f"\nDescription:\n{description}\n", file=sys.stderr)

    print("Generating fantasy image with Gemini...", file=sys.stderr)
    result = generate_image(description, image, temperature=args.img_temp)

    if result is not None:
        output_path = str(getattr(result, "path", result))
        update_run(
            conn,
            run_id,
            output_image_path=output_path,
            image_model_name=IMAGE_MODEL,
            img_temp=args.img_temp,
        )
        print(output_path)
    else:
        print("Image generation failed.", file=sys.stderr)
