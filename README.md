# imagemine

Transform any photo into a fantasy image. imagemine uses Claude to write a surrealist story about your photo, then generates a new image from that description using Gemini.

## How it works

1. Resize input image to max 1024px (preserving aspect ratio) and save to disk
2. Upload to Claude Sonnet via the Files API; generate a short surrealist story and image prompt
3. Pass the story + original image to Gemini (Nano Banana Pro) to generate the fantasy version
4. Save all run metadata — input, resized path, description, output path, models, temperatures — to a local SQLite database (`imagemine.db`)

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Setup

```sh
git clone <repo-url>
cd imagemine
uv pip install -e .
```

## API keys

Keys are resolved in this order on each run:

1. **Database** — stored in `imagemine.db` after first entry
2. **Environment variables** — `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
3. **Interactive prompt** — if neither is found, you are prompted and the value is saved to the database for future runs

To set keys ahead of time via environment:

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

### Options

```
usage: imagemine [-h] [--output-dir OUTPUT_DIR] [--desc-temp DESC_TEMP] [--img-temp IMG_TEMP] image_path

positional arguments:
  image_path            Path to input image

options:
  --output-dir          Output directory (default: current directory)
  --desc-temp           Sampling temperature for description generation (default: 1.0)
  --img-temp            Sampling temperature for image generation (default: 1.0)
```

### Examples

```sh
# Basic usage
imagemine sunset.jpg

# Custom output directory
imagemine photo.jpg --output-dir ~/Desktop/imagemine-out

# Tune creativity
imagemine photo.jpg --desc-temp 1.5 --img-temp 0.8

# Redirect description to a file, output path to stdout
imagemine photo.jpg 2>story.txt
```

### Run without installing

```sh
uv run imagemine path/to/photo.jpg
```

## Project layout

```
src/
  imagemine/
    _core.py       # constants and image resizing
    _db.py         # SQLite helpers (runs + config tables)
    _describe.py   # Claude description generation
    _generate.py   # Gemini image generation
    cli.py         # argument parsing and pipeline orchestration
    __main__.py    # python -m imagemine entry point
```

## Database

Every run is recorded in `imagemine.db` (created in the working directory). The `runs` table tracks:

| Column | Description |
|---|---|
| `input_file_path` | Absolute path to the source image |
| `resized_file_path` | Path to the saved resized JPEG |
| `generated_description` | Story + image prompt from Claude |
| `description_model_name` | Claude model used |
| `desc_temp` | Temperature used for description generation |
| `output_image_path` | Path to the generated image |
| `image_model_name` | Gemini model used |
| `img_temp` | Temperature used for image generation |

If a source image path already has a description stored, Claude is skipped and the cached description is reused.
