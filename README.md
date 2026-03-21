# imagemine

[![PyPI](https://img.shields.io/pypi/v/imagemine.svg)](https://pypi.org/project/imagemine/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![CI](https://github.com/hbmartin/imagemine/actions/workflows/ci.yml/badge.svg)](https://github.com/hbmartin/imagemine/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/hbmartin/imagemine/graph/badge.svg?token=prrlAXa92n)](https://codecov.io/gh/hbmartin/imagemine)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hbmartin/imagemine)


Transform any photo into something new. imagemine uses Claude to write a surrealist story about your photo, then generates a new image from that description using Gemini / Nano Banana.

## Table of Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [API keys](#api-keys)
- [CLI flags](#cli-flags)
- [Styles](#styles)
- [Character Mappings](#character-mappings)
- [Configuration](#configuration)
- [Apple TV screensaver](#apple-tv-screensaver)
- [Development](#development)
- [Legal](#legal)

## How it works

1. Resize input image to max 1024px (preserving aspect ratio) and save to disk
2. Send the resized image to Claude Sonnet via the Files API; generate a short surrealist story and image prompt
3. Pick a random visual style from the built-in style library (or specify one with `--style`)
4. Pass the story + style + resized image to Gemini to generate the re-imagined version
5. Save all run metadata to a local SQLite database (`~/.imagemine.db`)

## Requirements

- Python 3.14+
- An [Anthropic API key](https://console.anthropic.com/)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Quick Start

```sh
uvx imagemine path/to/photo.jpg
```

The generated image is saved to the current directory. The terminal UI shows each pipeline step with live spinners, elapsed timers, and a final summary panel.

### Installing

To use imagemine without invoking uvx, permanently install it as:

```sh
curl -LsSf uvx.sh/imagemine/install.sh | sh
imagemine path/to/photo.jpg
```

## API keys

Keys are resolved in this order on each run:

1. **Database** — stored in `~/.imagemine.db` after first entry
2. **Environment variables** — `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
3. **Interactive prompt** — if neither is found, you are prompted (input is masked) and the value is saved to the database for future runs

To set keys via environment:

```sh
export ANTHROPIC_API_KEY=sk-ant-...
export GEMINI_API_KEY=AI...
```

To set or update keys directly in the config database:

```sh
imagemine --config
```

## CLI flags

| Flag                  | Default    | Description                                              |
| --------------------- | ---------- | -------------------------------------------------------- |
| `image_path`          | —          | Path to input image (omit to use `--input-album`)        |
| `--input-album`       | DB / env   | macOS Photos album to pick a random input image from     |
| `--output-dir`        | `.`        | Directory to save the generated image                    |
| `--desc-temp`         | DB / `1.0` | Sampling temperature for Claude description generation   |
| `--img-temp`          | DB / `1.0` | Sampling temperature for Gemini image generation         |
| `--story TEXT`        | —          | Background context prepended to the Claude prompt when generating the image description             |
| `--style PROMPT`      | —          | Use PROMPT as the style instead of a randomly selected one from the database                        |
| `--fresh`             | off        | Pick style randomly from the least-used styles (ignored when `--style` is given)                    |
| `--choose-style`      | off        | Interactively pick style(s) from a numbered table before running the pipeline                       |
| `--list-styles`       | —          | Show all styles in the database as a table and exit      |
| `--add-style`         | —          | Interactively add a new style to the database and exit   |
| `--remove-style`      | —          | Interactively select and remove styles from the database and exit |
| `--aspect-ratio RATIO`| DB / env / `4:3` | Aspect ratio for generated image (see [supported ratios](https://ai.google.dev/gemini-api/docs/image-generation#aspect_ratios_and_image_size), e.g. `1:1`, `3:4`, `4:3`, `9:16`, `16:9`) |
| `--add-character-mapping` | — | Interactively add a character name mapping and exit |
| `--remove-character-mapping` | — | Interactively remove character name mapping(s) and exit |
| `--list-character-mappings` | — | Show all character name mappings and exit |
| `--destination-album` | DB / env   | macOS Photos album to import the generated image into    |
| `--silent`            | off        | Suppress Rich UI; only print the output file path        |
| `--json`              | off        | Output run results as JSON (suppresses Rich UI)          |
| `--config`            | —          | Interactively configure settings and exit                |
| `--history`           | —          | Show recent runs as a table and exit                     |
| `--config-path`       | `~/.imagemine.db` | Path to the SQLite database file                  |
| `--launchd [MINUTES]` | —          | Write a launchd plist to `~/Library/LaunchAgents/imagemine.plist` that runs imagemine on the given interval; omit `MINUTES` to be prompted. Prints the `launchctl` command to activate it. |

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

# Use a custom style prompt instead of a random one
imagemine photo.jpg --style "Ukiyo-e woodblock print, bold outlines, flat color"

# Generate with a specific aspect ratio
# Must be one of: https://ai.google.dev/gemini-api/docs/image-generation#aspect_ratios_and_image_size
imagemine photo.jpg --aspect-ratio 16:9

# List all styles in the database
imagemine --list-styles

# Add a new style interactively
imagemine --add-style

# Pick style(s) interactively from a numbered table
imagemine photo.jpg --choose-style

# Silent mode — only prints the output file path
imagemine photo.jpg --silent

# JSON mode — output run results as structured JSON
imagemine photo.jpg --json

# Save an SVG of the terminal session alongside the generated image
imagemine photo.jpg --session-svg

# Show recent run history with timing sparklines
imagemine --history

# Configure API keys and settings interactively
imagemine --config

# Use a custom database location
imagemine photo.jpg --config-path ~/work/imagemine.db

# Configure settings into a custom database
imagemine --config --config-path ~/work/imagemine.db
```

## Styles

Each run applies a randomly selected visual style from a built-in library of 35+ styles. The style name and description are appended to the image prompt sent to Gemini.

Example styles: Watercolor, 8-Bit Pixel Art, Ukiyo-e Woodblock, Neon Noir, Tarot Card, Vaporwave, Glitch Art, Renaissance Painting, and more.

### Choosing styles interactively

```sh
imagemine photo.jpg --choose-style
```

Displays a numbered table of all styles. Enter one number (e.g. `3`) to use that style, or a comma-separated list (e.g. `1,5,12`) to blend the selected styles into a single prompt. Each selected style's usage count is incremented.

### Using a custom style prompt

Use `--style` to pass a free-form style prompt directly instead of picking one at random from the database. imagemine will describe the photo, append the style text, and generate the image.

```sh
imagemine photo.jpg --style "Risograph print, grainy ink, limited overlapping spot colors"
```

### Listing styles

```sh
imagemine --list-styles
```

Prints a table of all styles in the database with their description and usage count.

### Adding a style

```sh
imagemine --add-style
```

Prompts for a name and a description/prompt, then saves the new style to the database. It will be included in random selection on future runs.

### Removing a style

```sh
imagemine --remove-style
```

Displays a numbered table of all styles. Enter one or more numbers (e.g. `1` or `1,3,5`), review the confirmation prompt, and confirm to delete.

## Character Mappings

When imagemine picks a photo from a macOS Photos album, it reads any face-detection names associated with the photo. Character mappings let you rename these before they reach the AI prompt — for example, mapping "John Smith" to "Captain America".

### Adding a mapping

```sh
imagemine --add-character-mapping
# Input name (from Photos): John Smith
# Mapped name (for prompt): Captain America
```

### Listing mappings

```sh
imagemine --list-character-mappings
```

### Removing mappings

```sh
imagemine --remove-character-mapping
```

Displays a numbered list of mappings. Enter one or more numbers to remove, then confirm.

## Configuration

Run the interactive config wizard to set or update any value:

```sh
imagemine --config
```

The wizard walks through each key in order, pre-populates non-secret fields with their current values, and masks API key input. Leaving a field blank keeps the existing value (or skips it if unset).


| Key                 | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `ANTHROPIC_API_KEY` | Anthropic API key (checked before env var)                   |
| `GEMINI_API_KEY`    | Google Gemini API key (checked before env var)               |
| `DEFAULT_DESC_TEMP` | Default sampling temperature for description generation (e.g. `1.2`) |
| `DEFAULT_IMG_TEMP`  | Default sampling temperature for image generation (e.g. `0.8`) |
| `CLAUDE_MODEL`      | Claude model to use for description (default: `claude-sonnet-4-6`) |
| `GEMINI_MODEL`      | Gemini model to use for image generation (default: `gemini-3-pro-image-preview`) |
| `INPUT_ALBUM`       | macOS Photos album to pick a random input image from         |
| `DESTINATION_ALBUM` | macOS Photos album name to import generated images into      |
| `ASPECT_RATIO`      | Aspect ratio for generated images (default: `4:3`); must be a ratio listed at [the Gemini docs](https://ai.google.dev/gemini-api/docs/image-generation#aspect_ratios_and_image_size) |

## Apple TV screensaver

You can use imagemine to generate a living screensaver on Apple TV by continuously transforming photos from one album and depositing the results into another.

### Setup

1. In macOS Photos, create two albums — one for source photos (e.g. `Camera Roll`) and one for the generated output (e.g. `imagemine`). Make the output album a Shared Album so Apple TV can see it.

2. Configure imagemine to read from the source album and write to the output album:

```sh
imagemine --config
```

3. Run imagemine on a schedule via launchd to keep the output album growing. Use the `--launchd` flag to write the agent configuration automatically:

```sh
imagemine --launchd 30
```

Pass a number of minutes as the argument. If you omit it, imagemine will prompt you:

```sh
imagemine --launchd
# Run interval (minutes): 30
```

Both commands write `~/Library/LaunchAgents/imagemine.plist` and print the `launchctl` command to activate it. Pass `--config-path` to use a non-default database location:

```sh
imagemine --launchd 30 --config-path ~/work/imagemine.db
```

Then follow the printed instructions to load the agent:

```sh
launchctl load ~/Library/LaunchAgents/imagemine.plist
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

To run from the local source:

```sh
uv run imagemine path/to/photo.jpg
```

Run the linters, type checker, and tests:

```sh
uv run ruff check src --fix
uv run pyrefly check src
uv run ty check src
uv run pytest tests/
```

### Database

Every run is recorded in `~/.imagemine.db` by default. Use `--config-path` to specify a different location. The `runs` table tracks:

| Column                   | Description                                                  |
| ------------------------ | ------------------------------------------------------------ |
| `started_at`             | UTC timestamp when the run began                             |
| `input_file_path`        | Absolute path to the source image                            |
| `resized_file_path`      | Path to the temporary resized JPEG (deleted after generation) |
| `generated_description`  | Story + image prompt from Claude                             |
| `description_model_name` | Claude model used                                            |
| `desc_temp`              | Temperature used for description generation                  |
| `desc_gen_ms`            | Description generation time in milliseconds                  |
| `output_image_path`      | Path to the generated image                                  |
| `image_model_name`       | Gemini model used                                            |
| `img_temp`               | Temperature used for image generation                        |
| `img_gen_ms`             | Image generation time in milliseconds                        |
| `input_album_photo_id`   | Photos item ID when input was selected from an album         |
| `style`                  | Visual style applied to the image prompt                     |

A new description is generated from Claude on every run.

### Terminal UI

imagemine uses [Rich](https://github.com/Textualize/rich) for its terminal output:

- **Labeled section rules** divide the pipeline into phases: Resize → Describe → Style → Generate
- **Live spinners with elapsed timers** show progress during the two API calls — a `moon` spinner for Claude description generation and a `smiley` spinner for Gemini image generation
- **Description panel** renders the generated story as formatted Markdown inside a cyan-bordered panel
- **Style tree** shows the randomly selected style with its full description
- **Summary panel** displays source file, style, per-step timing, total wall time, and output path
- **`--history` table** lists recent runs with per-step timing, total time, and a proportional sparkline bar
- **`--session-svg`** saves a styled SVG of the entire terminal session alongside the generated image
- **Error tracebacks** are rendered with Rich syntax highlighting when an API call fails

## Legal

Copyright 2026 [Harold Martin](https://www.linkedin.com/in/harold-martin-98526971/). Licensed under the [Apache License, Version 2.0](LICENSE).

Apple, Apple TV, and Photos are trademarks of Apple Inc., registered in the U.S. and other countries.

Claude and Anthropic are trademarks of Anthropic, PBC.

Google and Gemini are trademarks of Google LLC.

This project is not affiliated with, endorsed by, or sponsored by Apple Inc., Anthropic, PBC, or Google LLC.
