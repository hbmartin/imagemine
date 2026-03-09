import pathlib

from PIL import Image, PngImagePlugin


def write_png_metadata(path: str, description: str) -> None:
    img = Image.open(path)
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Description", description)
    img.save(path, pnginfo=png_info)


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
