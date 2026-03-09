import pathlib
import sys
import tempfile
import time
from typing import TYPE_CHECKING

import anthropic
from anthropic.types.beta import BetaTextBlock

from ._core import DESCRIPTION_MODEL
from ._db import avg_duration_ms, lookup_description, update_run

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

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
"""


def describe_image(
    image: Image.Image,
    temperature: float = 2.0,
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


def _get_description(  # noqa: PLR0913
    conn: sqlite3.Connection,
    run_id: int,
    image: Image.Image,
    input_path: str,
    desc_temp: float,
    api_key: str,
    *,
    force: bool,
    log: Callable[[str], None],
    err: Callable[[str], None],
) -> str:
    """Return a description, from cache or freshly generated."""
    if not force:
        cached = lookup_description(conn, input_path)
        if cached:
            log("Reusing cached description from previous run.")
            return cached

    avg = avg_duration_ms(conn, "desc_gen_ms")
    avg_str = f" (avg time: {avg / 1000:.1f}s)" if avg is not None else ""
    log(f"Generating fantastical description with Claude...{avg_str}")
    t0 = time.monotonic()
    try:
        description = describe_image(image, temperature=desc_temp, api_key=api_key)
    except Exception as e:  # noqa: BLE001
        err(f"Description generation failed: {e}")
        sys.exit(1)
    desc_gen_ms = round((time.monotonic() - t0) * 1000)
    update_run(
        conn,
        run_id,
        generated_description=description,
        description_model_name=DESCRIPTION_MODEL,
        desc_temp=desc_temp,
        desc_gen_ms=desc_gen_ms,
    )
    return description
