"""Style library and database helpers for the styles table."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

if TYPE_CHECKING:
    import sqlite3

STYLES = [
    ("Photorealistic", "crisp detail, natural lighting, true-to-life textures"),
    ("Watercolor", "soft wet edges, blooming pigment, delicate paper texture"),
    ("8-Bit Pixel Art", "chunky pixels, limited palette, retro arcade aesthetic"),
    ("Hand-Drawn Sketch", "loose pencil lines, cross-hatching, rough paper grain"),
    ("Victorian Portrait", "ornate gilded frame, sepia tones, formal studio staging"),
    ("3D Render", "Pixar-style, rounded forms, soft studio lighting"),
    ("Y2K Chrome", "iridescent metallics, bubbly fonts, early-internet maximalism"),
    ("Ukiyo-e Woodblock", "bold outlines, flat color, Japanese Edo-period aesthetic"),
    (
        "Impressionist Oil",
        "loose visible brushstrokes, dappled light, Monet-style color",
    ),
    ("Stained Glass", "bold lead lines, jewel-toned backlit color, gothic tracery"),
    ("Pulp Magazine Cover", "halftone dots, dramatic shadows, bold 1950s serif type"),
    (
        "Claymation",
        "tactile clay textures, fingerprint imperfections, warm studio lighting",
    ),
    ("Neon Noir", "rain-slicked streets, pink and cyan glow, deep cinematic shadows"),
    (
        "Children's Picture Book",
        "gouache illustration, chunky shapes, Quentin Blake looseness",
    ),
    (
        "Botanical Illustration",
        "fine ink linework, hand-labeled, 18th-century naturalist style",
    ),
    (
        "Tarot Card",
        "symbolic iconography, ornate border, rich jewel tones, mystical composition",
    ),
    (
        "Risograph Print",
        "grainy ink texture, limited overlapping spot colors, indie zine aesthetic",
    ),
    ("Low-Poly 3D", "geometric facets, flat-shaded triangles, clean minimal palette"),
    (
        "1970s Groovy Poster",
        "psychedelic swirls, warm earth tones, rounded bubble lettering",
    ),
    (
        "Cave Painting",
        "ochre and charcoal, rough stone texture, primitive silhouette style",
    ),
    ("Meme Format", "bold white Impact font, black outline text, classic macro layout"),
    (
        "Album Cover",
        "centered subject, minimal negative space, stark typographic treatment",
    ),
    (
        "Dadaist Collage",
        "clashing cut-and-paste elements, absurdist juxtaposition, chaotic composition",
    ),
    (
        "Renaissance Painting",
        "dramatic chiaroscuro, heavenly light rays, cherubs optional",
    ),
    (
        "IKEA Instruction Manual",
        "flat line art, no faces, numbered steps, sans-serif minimal",
    ),
    (
        "Propaganda Poster",
        "bold graphic shapes, limited palette, heroic upward gaze, stark silhouette",
    ),
    (
        "Paper Cutout",
        "Layered cardstock, distinct physical depth, soft top-down shadows, craft-store aesthetic.",  # noqa: E501
    ),
    (
        "Needle Felted",
        "Fuzzy wool textures, soft organic shapes, matte fibrous surface, handcrafted toy vibe.",  # noqa: E501
    ),
    (
        "Art Deco Travel Poster",
        "Geometric symmetry, streamlined elegance, matte gradients, 1920s luxury.",
    ),
    (
        "Bauhaus",
        'Primary colors (red, blue, yellow), rigid geometric shapes, functional minimalism, "San-Serif" influence.',  # noqa: E501
    ),
    (
        "Fauvism",
        "Non-naturalistic wild colors, thick painterly brushstrokes, emotional intensity over realism.",  # noqa: E501
    ),
    (
        "Vaporwave",
        "80s marble statues, glitchy VHS artifacts, pastel sunsets, 90s shopping mall nostalgia.",  # noqa: E501
    ),
    (
        "Isometric Voxel Art",
        '3D pixel cubes, "Crossy Road" perspective, clean grid alignment, toy-like miniature world.',  # noqa: E501
    ),
    (
        "Double Exposure",
        "Two images overlaid, silhouette-masking, dreamy transparency, metaphorical composition.",  # noqa: E501
    ),
    (
        "Glitch Art",
        'Data corruption artifacts, shifted color channels, interlaced scanlines, "cyber-decay" aesthetic.',  # noqa: E501
    ),
    (
        "Abstract Expressionism",
        "chaotic drips and splatters, bold gestural strokes, emotional raw canvas, Pollock-inspired",  # noqa: E501
    ),
    (
        "Art Nouveau",
        "flowing organic lines, intricate floral motifs, elegant curves, Alphonse Mucha elegance",  # noqa: E501
    ),
    (
        "Celtic Knot",
        "interwoven patterns, infinite loops, illuminated manuscript borders, medieval symbolism",  # noqa: E501
    ),
    (
        "Comic Strip",
        "paneled layout, speech bubbles, bold onomatopoeia, sequential storytelling",
    ),
    (
        "Cubism",
        "fragmented angular forms, multiple viewpoints, muted earthy tones, Picasso geometry",  # noqa: E501
    ),
    (
        "Cyberpunk",
        "dystopian high-tech, flickering holograms, gritty urban decay, blade runner neon",  # noqa: E501
    ),
    (
        "Egyptian Hieroglyph",
        "flat profile figures, symbolic icons, papyrus texture, ancient Nile palette",
    ),
    (
        "Graffiti Street Art",
        "spray-paint drips, bold tags, urban wall texture, stencil overlays",
    ),
    (
        "Mosaic Tile",
        "tiny colored shards, grout lines, shimmering irregular patterns, Byzantine gleam",  # noqa: E501
    ),
    (
        "Origami Fold",
        "sharp paper creases, geometric polygons, floating shadow depth, minimalist craft",  # noqa: E501
    ),
    (
        "Pointillism",
        "dense color dots, optical blending, vibrant Seurat landscapes, stippled texture",  # noqa: E501
    ),
    (
        "Steampunk",
        "brass gears and pipes, Victorian leather, foggy industrial haze, retro-futuristic gadgets",  # noqa: E501
    ),
    (
        "Surrealism",
        "dreamlike impossibilities, floating elements, Dali melting clocks, subconscious symbolism",  # noqa: E501
    ),
    (
        "Vintage Ad",
        "retro 1950s illustrations, cheerful spot colors, kitschy slogans, magazine gloss",  # noqa: E501
    ),
]


def random_style(conn: sqlite3.Connection) -> tuple[str, str] | tuple[None, None]:
    row = conn.execute(
        "SELECT name, description FROM styles ORDER BY RANDOM() LIMIT 1",
    ).fetchone()
    if row:
        return row[0], row[1]
    return None, None


def get_all_styles(conn: sqlite3.Connection) -> list[tuple[str, str, int, str]]:
    """Return all styles as (name, description, used_count, created_at) sorted by name."""  # noqa: E501
    return conn.execute(
        "SELECT name, description, used_count, created_at FROM styles ORDER BY name",
    ).fetchall()


def add_style(conn: sqlite3.Connection, name: str, description: str) -> None:
    """Insert or replace a style, preserving its existing used_count."""
    conn.execute(
        "INSERT OR REPLACE INTO styles (name, description, used_count)"
        " VALUES (?, ?, COALESCE((SELECT used_count FROM styles WHERE name = ?), 0))",
        (name, description, name),
    )
    conn.commit()


def remove_style(conn: sqlite3.Connection, name: str) -> None:
    """Delete a style by name."""
    conn.execute("DELETE FROM styles WHERE name = ?", (name,))
    conn.commit()


def increment_style_count(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "UPDATE styles SET used_count = used_count + 1 WHERE name = ?",
        (name,),
    )
    conn.commit()


def _run_add_style(conn: sqlite3.Connection) -> None:
    """Interactively prompt for a new style name and description, then save it."""
    console = Console()
    console.print(Rule("[bold magenta]Add style[/]"))

    name = Prompt.ask("[bold]Style name[/]")
    if not name.strip():
        console.print("[bold red]Error:[/] Name is required.")
        sys.exit(1)

    description = Prompt.ask("[bold]Style description / prompt[/]")
    if not description.strip():
        console.print("[bold red]Error:[/] Description is required.")
        sys.exit(1)

    add_style(conn, name.strip(), description.strip())
    console.print(f"\n  [green]✓[/] Style [magenta]{name.strip()}[/] saved.")


def _run_remove_style(conn: sqlite3.Connection) -> None:
    """Interactively select and confirm removal of one or more styles."""
    console = Console()
    console.print(Rule("[bold magenta]Remove style[/]"))

    styles = get_all_styles(conn)
    if not styles:
        console.print("[dim]No styles found.[/]")
        return

    table = Table(show_lines=True, border_style="dim")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="magenta")
    table.add_column("Description", style="dim")
    table.add_column("Used", justify="right", style="yellow")

    for i, (name, description, used_count, _) in enumerate(styles, 1):
        table.add_row(str(i), name, description, str(used_count))

    console.print(table)

    raw = Prompt.ask(
        "\n[bold]Enter number(s) to remove[/] [dim](e.g. 1 or 1,3,5)[/]",
        default="",
    )
    if not raw.strip():
        console.print("[dim]Cancelled.[/]")
        return

    try:
        indices = [int(s.strip()) for s in raw.split(",") if s.strip()]
    except ValueError:
        console.print("[bold red]Error:[/] Invalid selection — enter numbers only.")
        sys.exit(1)

    to_remove: list[str] = []
    for idx in indices:
        if idx < 1 or idx > len(styles):
            console.print(f"[bold red]Error:[/] {idx} is out of range.")
            sys.exit(1)
        to_remove.append(styles[idx - 1][0])

    console.print("\nStyles to remove:")
    for style_name in to_remove:
        console.print(f"  [magenta]{style_name}[/]")

    confirm = Prompt.ask(
        "\n[bold red]Delete these styles?[/]",
        choices=["y", "n"],
        default="n",
    )
    if confirm != "y":
        console.print("[dim]Cancelled.[/]")
        return

    for style_name in to_remove:
        remove_style(conn, style_name)

    console.print(f"\n  [green]✓[/] Removed {len(to_remove)} style(s).")
