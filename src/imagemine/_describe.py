import pathlib
import tempfile
from typing import TYPE_CHECKING

import anthropic
from anthropic.types.beta import BetaTextBlock

from ._core import DESCRIPTION_MODEL

if TYPE_CHECKING:
    from PIL import Image

PROMPT = """
You are a surrealist writer. Look at this photo carefully, the specific details matter.
(e.g. the dog's motivations, expression, body language, and surroundings.)
Before writing, identify the single funniest true thing about this specific photo. Build everything from that.

A few hours after this photo was taken, something fun and crazy happened!
Write a short, punchy story (about 3 sentences) about what happened.
The story should be fun and uplifting. Never include negative or scary elements.

Rules:
- The twist must be specific to what's actually in the photo, not generic
- The main subject(s) should be the cause of the chaos, not the victim of it
- It should be funny and strange, not spooky or epic
- At least one sentence must be completely unexpected
- Give the subject (dog) an unexpectedly specific internal monologue (not "he was excited" — "he had been planning this since Tuesday")
- Include one detail that is weirdly mundane amid the chaos
- The final sentence should land like a punchline

Begin the story mid-action, not with setup.

After the story, output a section starting with "IMAGE:"
This section describes the single most creative or hilarious moment from the scene.

## Style Suggestions (be creative and imagine more of these best suited to the story)
- Photo realistic (match original)
- Watercolor
- 8-Bit Pixel Art
- Hand-Drawn Sketch
- Vintage Victorian Portrait: vintage aesthetic, detailed realism
- 3D Render: stylized character portrait with highly detailed Pixar-style character design, soft studio lighting, ultra-sharp, cinematic render.
- Y2K Chrome & Plush Fusion
- Ukiyo-e Woodblock Print: bold outlines, flat color, Japanese edo-period aesthetic
- Impressionist Oil Painting: loose brushwork, Monet-style dappled light
- Stained Glass Window: bold lead lines, jewel-toned backlit color
- 1950s Pulp Magazine Cover: halftone dots, dramatic shadows, bold serif title font
- Claymation / Stop Motion: tactile clay textures, fingerprint imperfections, warm studio lighting
- Neon Noir: rain-slicked streets, pink/cyan neon glow, cinematic shadows
- Children's Picture Book: gouache illustration, chunky shapes, Quentin Blake-style looseness

Rules for the IMAGE description:
- If the scene is absurd, lean into contrast: pair the chaos with one completely unbothered bystander
- Describe the subject's face as if it's a human actor hitting their best moment
- Add a foreground detail that frames the chaos
- Describe only what a camera would literally capture at that instant
- Be specific: include e.g. expressions and absurd physical details
- Include Hyper-Specific details that make the scene come alive. More detail is better.
- Provide Context and Intent: Explain the purpose of the image.
- Use Step-by-Step Instructions: For complex scenes with many elements, break down steps
Control the Camera: Use photographic and cinematic language to control the composition.
- Last line: [subject doing thing], [environment], [style]
"""


def describe_image(
    image: Image.Image,
    temperature: float = 1.0,
    api_key: str | None = None,
) -> str:
    client = anthropic.Anthropic(api_key=api_key)

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
