import pathlib
import sys
import time
from typing import TYPE_CHECKING

from gemimg import GemImg

from ._core import IMAGE_MODEL
from ._db import avg_duration_ms, update_run

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

    from gemimg import ImageGen  # type: ignore[import-not-found]
    from PIL import Image


def generate_image(
    description: str,
    image: Image.Image,
    api_key: str,
    temperature: float = 1.0,
    save_dir: str = "",
) -> ImageGen | None:
    g = GemImg(model=IMAGE_MODEL, api_key=api_key)
    return g.generate(
        description,
        image,
        aspect_ratio="4:3",
        temperature=temperature,
        save_dir=save_dir,
    )


def _run_generation(  # noqa: PLR0913
    conn: sqlite3.Connection,
    run_id: int,
    description: str,
    image: Image.Image,
    img_temp: float,
    api_key: str,
    output_dir: pathlib.Path,
    *,
    log: Callable[[str], None],
    err: Callable[[str], None],
) -> str:
    """Generate image, validate output exists, update DB, return output path."""
    avg = avg_duration_ms(conn, "img_gen_ms")
    avg_str = f" (avg time: {avg / 1000:.1f}s)" if avg is not None else ""
    log(f"Generating fantasy image with Gemini...{avg_str}")
    t0 = time.monotonic()
    try:
        result = generate_image(
            description,
            image,
            api_key=api_key,
            temperature=img_temp,
            save_dir=str(output_dir),
        )
    except Exception as e:  # noqa: BLE001
        err(f"Image generation failed: {e}")
        sys.exit(1)
    img_gen_ms = round((time.monotonic() - t0) * 1000)

    if result is None:
        err("Image generation returned no result.")
        sys.exit(1)

    from gemimg import ImageGen  # noqa: PLC0415

    if not isinstance(result, ImageGen) or not result.image_path:
        err(f"Image generation returned unexpected result: {result!r}")
        sys.exit(1)

    output_path = result.image_path
    log(f"Image written to: {output_path}")

    if not pathlib.Path(output_path).exists():
        err(f"Generated image not found at expected path: {output_path}")
        sys.exit(1)

    update_run(
        conn,
        run_id,
        output_image_path=output_path,
        image_model_name=IMAGE_MODEL,
        img_temp=img_temp,
        img_gen_ms=img_gen_ms,
    )
    return output_path
