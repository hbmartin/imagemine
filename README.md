# imagemine

[![PyPI](https://img.shields.io/pypi/v/imagemine.svg)](https://pypi.org/project/imagemine/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![CI](https://github.com/hbmartin/imagemine/actions/workflows/ci.yml/badge.svg)](https://github.com/hbmartin/imagemine/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hbmartin/imagemine)


Transform any photo into a fantastical image. imagemine uses Claude to write a surrealist story about your photo, then generates a new image from that description using Gemini / Nano Banana.

## How it works

1. Resize input image to max 1024px (preserving aspect ratio) and save to disk
2. Send to Claude Sonnet via the Files API; generate a short surrealist story and image prompt
3. Pick a random visual style from the built-in style library (or specify one with `--style`)
4. Pass the story + style + original image to Gemini to generate the fantasy version
5. Save all run metadata to a local SQLite database (`imagemine.db`)

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Setup

```sh
uvx imagemine path/to/photo.jpg
```

```sh
uv run imagemine path/to/photo.jpg
```

## API keys

Keys are resolved in this order on each run:

1. **Database** — stored in `imagemine.db` after first entry
2. **Environment variables** — `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
3. **Interactive prompt** — if neither is found, you are prompted and the value is saved to the database for future runs

To set keys via environment:

```sh
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=AI...
```

To set or update keys directly in the database:

```sh
sqlite3 imagemine.db "INSERT OR REPLACE INTO config (key, value) VALUES ('ANTHROPIC_API_KEY', 'sk-ant-...');"
sqlite3 imagemine.db "INSERT OR REPLACE INTO config (key, value) VALUES ('GEMINI_API_KEY', 'AI...');"
```

## Usage

```sh
imagemine path/to/photo.jpg
```

The generated image is saved to the current directory. The story and image prompt are printed to stderr; the output file path is printed to stdout.

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `image_path` | — | Path to input image (omit to use `--input-album`) |
| `--input-album` | DB / env | macOS Photos album to pick a random input image from |
| `--output-dir` | `.` | Directory to save the generated image |
| `--desc-temp` | DB / `1.0` | Sampling temperature for Claude description generation |
| `--img-temp` | DB / `1.0` | Sampling temperature for Gemini image generation |
| `--style` | random | Visual style to apply (overrides random style selection) |
| `--destination-album` | DB / env | macOS Photos album to import the generated image into |
| `--force` | off | Ignore cached description and regenerate from scratch |
| `--silent` | off | Suppress all printed output |

### Examples

```sh
# Basic usage
imagemine sunset.jpg

# Pick a random photo from a Photos album
imagemine --input-album "Camera Roll"

# Custom output directory
imagemine photo.jpg --output-dir ~/Desktop/imagemine-out

# Tune creativity
imagemine photo.jpg --desc-temp 1.5 --img-temp 0.8

# Use a specific style
imagemine photo.jpg --style "Ukiyo-e Woodblock"

# Re-run on the same photo, ignoring the cached description
imagemine photo.jpg --force

# Silent mode — no output, just runs and records to DB
imagemine photo.jpg --silent

# Redirect story to a file, output path to stdout
imagemine photo.jpg 2>story.txt
```

## Styles

Each run applies a randomly selected visual style from a built-in library of 35+ styles. The style is appended to the image prompt sent to Gemini.

Example styles: Watercolor, 8-Bit Pixel Art, Ukiyo-e Woodblock, Neon Noir, Tarot Card, Vaporwave, Glitch Art, Renaissance Painting, and more.

To lock in a style for a run, use `--style`:

```sh
imagemine photo.jpg --style "Risograph Print"
```

To add or remove styles, edit the `styles` table in `imagemine.db`:

```sh
# List styles
sqlite3 imagemine.db "SELECT name FROM styles;"

# Add a custom style
sqlite3 imagemine.db "INSERT INTO styles (name, description) VALUES ('Lego Brick', 'Chunky ABS plastic bricks, primary colors, stud texture, classic minifig proportions.');"

# Remove a style
sqlite3 imagemine.db "DELETE FROM styles WHERE name = 'Meme Format';"
```

## Configuration

All configuration is stored in the `config` table of `imagemine.db`. Use `INSERT OR REPLACE` to set or update any value:

```sh
sqlite3 imagemine.db "INSERT OR REPLACE INTO config (key, value) VALUES ('<key>', '<value>');"
```

| Key | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (checked before env var) |
| `GEMINI_API_KEY` | Google Gemini API key (checked before env var) |
| `DEFAULT_DESC_TEMP` | Default sampling temperature for description generation (e.g. `1.2`) |
| `DEFAULT_IMG_TEMP` | Default sampling temperature for image generation (e.g. `0.8`) |
| `INPUT_ALBUM` | macOS Photos album to pick a random input image from |
| `DESTINATION_ALBUM` | macOS Photos album name to import generated images into |

## Apple TV screensaver

You can use imagemine to generate a living screensaver on Apple TV by continuously transforming photos from one album and depositing the results into another.

### Setup

1. In macOS Photos, create two albums — one for source photos (e.g. `Camera Roll`) and one for the generated output (e.g. `imagemine`). Make the output album a Shared Album so Apple TV can see it.

2. Configure imagemine to read from the source album and write to the output album:

```sh
sqlite3 imagemine.db "INSERT OR REPLACE INTO config (key, value) VALUES ('INPUT_ALBUM', 'Camera Roll');"
sqlite3 imagemine.db "INSERT OR REPLACE INTO config (key, value) VALUES ('DESTINATION_ALBUM', 'imagemine');"
```

3. Run imagemine on a schedule (e.g. via cron) to keep the output album growing:

```sh
# Add a new fantasy image every 30 minutes
*/30 * * * * cd /path/to/project && uv run imagemine >> /tmp/imagemine.log 2>&1
```

### Setting the screensaver on Apple TV

1. Open the **Photos** app on Apple TV 4K.
2. Navigate to **Shared Albums** or **Albums** at the top of the screen.
3. Select the output album (`imagemine`), then select **Set as Screen Saver** and confirm.

New images added to the shared album will appear in the screensaver automatically.

## Development

### Setup

```sh
git clone https://github.com/hbmartin/imagemine
cd imagemine
uv sync --dev
```

Run the linters and type checker:

```sh
uv run black src
uv run ruff check src --fix
uv run pyrefly check src
```

Run the tests:

```sh
uv run pytest tests/
```

### Project layout

```
src/
  imagemine/
    _album.py      # macOS Photos integration (input/output album via osascript)
    _config.py     # argument parsing and config resolution
    _core.py       # constants and image resizing
    _db.py         # SQLite helpers (runs, styles, and config tables)
    _describe.py   # Claude description generation
    _generate.py   # Gemini image generation
    cli.py         # pipeline orchestration entry point
    __main__.py    # python -m imagemine entry point
```

### Database

Every run is recorded in `imagemine.db` (created in the working directory). The `runs` table tracks:

| Column | Description |
|---|---|
| `started_at` | UTC timestamp when the run began |
| `input_file_path` | Absolute path to the source image |
| `resized_file_path` | Path to the temporary resized JPEG (deleted after generation) |
| `generated_description` | Story + image prompt from Claude |
| `description_model_name` | Claude model used |
| `desc_temp` | Temperature used for description generation |
| `desc_gen_ms` | Description generation time in milliseconds |
| `output_image_path` | Path to the generated image |
| `image_model_name` | Gemini model used |
| `img_temp` | Temperature used for image generation |
| `img_gen_ms` | Image generation time in milliseconds |
| `input_album_photo_id` | Photos item ID when input was selected from an album |
| `style` | Visual style applied to the image prompt |

If a source image path already has a description stored, Claude is skipped and the cached description is reused. Use `--force` to bypass this.

## Legal

Copyright 2026 [Harold Martin](https://www.linkedin.com/in/harold-martin-98526971/). Licensed under the [Apache License, Version 2.0](LICENSE).

Apple, Apple TV, and Photos are trademarks of Apple Inc., registered in the U.S. and other countries.

Claude and Anthropic are trademarks of Anthropic, PBC.

Google and Gemini are trademarks of Google LLC.

This project is not affiliated with, endorsed by, or sponsored by Apple Inc., Anthropic, PBC, or Google LLC.
