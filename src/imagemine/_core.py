import pathlib

from PIL import Image

DESCRIPTION_MODEL = "claude-sonnet-4-6"
IMAGE_MODEL = "gemini-3-pro-image-preview"
DB_PATH = pathlib.Path.home() / ".imagemine.db"


def resize_image(
    path: str,
    output_dir: pathlib.Path,
    max_size: int = 1024,
) -> tuple[Image.Image, pathlib.Path]:
    image = Image.open(path)
    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    stem = pathlib.Path(path).stem
    resized_path = output_dir / f"{stem}_resized.jpg"
    image.save(resized_path, format="JPEG")
    return image, resized_path
