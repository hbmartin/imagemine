import pathlib
import tempfile

import anthropic
from anthropic.types.beta import BetaTextBlock
from PIL import Image

from ._core import DESCRIPTION_MODEL

PROMPT = """
You are a surrealist writer. Look at this photo carefully, the specific details matter.
(e.g. the dog's motivations, expression, body language, and surroundings.)

A few hours after this photo was taken, something wild happened!
Write a short, punchy story (about 3 sentences) about what happened.

Rules:
- The twist must be specific to what's actually in the photo, not generic
- The main subject should be the cause of the chaos, not the victim of it
- It should be funny and/or strange, not spooky or epic
- At least one sentence must be completely unexpected
- No magic portals, dragons, or time travel — find a weirder angle

Begin the story mid-action, not with setup.

After the story, output a single line starting with "IMAGE:"
This line describes the single most creative or hilarious moment from the scene.

Rules for the IMAGE line:
- Written as a visual description only — no backstory, no "as if" or "about to"
- Describe only what a camera would literally capture at that instant
- Be specific: include e.g. expressions and absurd physical details
- Format: [subject doing thing], [environment], [style]
"""


def describe_image(image: Image.Image, temperature: float = 0.5) -> str:
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
            temperature=temperature,
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
                            "text": PROMPT,
                        },
                    ],
                },
            ],
            betas=["files-api-2025-04-14"],
        )
    finally:
        client.beta.files.delete(uploaded.id, betas=["files-api-2025-04-14"])

    for block in response.content:
        if isinstance(block, BetaTextBlock):
            return block.text
    msg = "No text block found in response"
    raise TypeError(msg)
