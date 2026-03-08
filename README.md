# imagemine

Transform any photo into a fantasy image. imagemine uses Claude to write a surrealist story about your photo, then generates a new image from that description using Gemini.

## How it works

1. Resize input image to max 1024px (preserving aspect ratio) and save to disk
2. Send to Claude Sonnet via base64; generate a short surrealist story and image prompt
3. Pass the story + original image to Gemini (Nano Banana Pro) to generate the fantasy version
4. Save all run metadata to a local SQLite database (`imagemine.db`)

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Setup

```sh
git clone <repo-url>
cd imagemine
uv sync
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

# Re-run on the same photo, ignoring the cached description
imagemine photo.jpg --force

# Silent mode — no output, just runs and records to DB
imagemine photo.jpg --silent

# Redirect story to a file, output path to stdout
imagemine photo.jpg 2>story.txt
```

### Run without installing

```sh
uv run imagemine path/to/photo.jpg
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

## Project layout

```
src/
  imagemine/
    _album.py      # macOS Photos integration (input/output album via osascript)
    _config.py     # argument parsing and config resolution
    _core.py       # constants and image resizing
    _db.py         # SQLite helpers (runs + config tables)
    _describe.py   # Claude description generation
    _generate.py   # Gemini image generation
    cli.py         # pipeline orchestration entry point
    __main__.py    # python -m imagemine entry point
```

## Database

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

If a source image path already has a description stored, Claude is skipped and the cached description is reused. Use `--force` to bypass this.
