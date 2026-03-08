from gemimg import GemImg
from PIL import Image

from ._core import IMAGE_MODEL


def generate_image(
    description: str, image: Image.Image, temperature: float = 1.0,
) -> object:
    g = GemImg(model=IMAGE_MODEL)
    return g.generate(description, image, temperature=temperature)
