from typing import TYPE_CHECKING

from gemimg import GemImg

from ._core import IMAGE_MODEL

if TYPE_CHECKING:
    from PIL import Image


def generate_image(
    description: str, image: Image.Image, temperature: float = 1.0,
) -> object:
    g = GemImg(model=IMAGE_MODEL)
    return g.generate(description, image, aspect_ratio="16:9", temperature=temperature)
