# imagemine

Transform any photo into a fantasy image. imagemine uses Claude to imagine a fantastical scenario based on your photo, then generates a new image from that description using Gemini.

## How it works

1. Resize input image to max 1024px (preserving aspect ratio)
2. Send to Claude Sonnet with the prompt: *"Imagine a fantastical scenario set an hour after this photo"*
3. Pass the description + original image to Gemini 2.5 Flash Image to generate the fantasy version

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An [Anthropic API key](https://console.anthropic.com/)
- A [Google Gemini API key](https://aistudio.google.com/apikey)

## Setup

```sh
# Clone the repo
git clone <repo-url>
cd imagemine

# Install dependencies
uv pip install -e .
```

## Usage

Set your API keys as environment variables:

```sh
export ANTHROPIC_API_KEY=your_anthropic_key
export GEMINI_API_KEY=your_gemini_key
```

Run the CLI:

```sh
imagemine path/to/photo.jpg
```

The generated image is saved to the current directory. The fantastical description is printed to stderr, and the output file path is printed to stdout.

### Options

```
usage: imagemine [-h] [--output-dir OUTPUT_DIR] image_path

positional arguments:
  image_path            Path to input image

options:
  --output-dir          Output directory (default: current directory)
```

### Examples

```sh
# Basic usage
imagemine sunset.jpg

# Redirect description to a file, image path to stdout
imagemine photo.jpg 2>description.txt

# One-liner with inline env vars
ANTHROPIC_API_KEY=... GEMINI_API_KEY=... imagemine photo.jpg
```

### Run without installing

```sh
ANTHROPIC_API_KEY=... GEMINI_API_KEY=... uv run main.py path/to/photo.jpg
```
