import pathlib
import sys

from PIL import Image, PngImagePlugin

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from imagemine._image import write_png_metadata


def test_write_png_metadata_preserves_existing_text_chunks(tmp_path) -> None:
    path = tmp_path / "example.png"
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Author", "Harold")
    png_info.add_text("Comment", "keep me")
    png_info.add_text("Description", "old description")

    Image.new("RGB", (4, 4), color="red").save(path, pnginfo=png_info)

    write_png_metadata(str(path), "new description")

    with Image.open(path) as image:
        assert image.text["Author"] == "Harold"
        assert image.text["Comment"] == "keep me"
        assert image.text["Description"] == "new description"
