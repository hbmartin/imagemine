import contextlib
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

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
]


def init_db(db_path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_file_path TEXT,
            resized_file_path TEXT,
            generated_description TEXT,
            description_model_name TEXT,
            desc_temp REAL,
            output_image_path TEXT,
            image_model_name TEXT,
            img_temp REAL,
            desc_gen_ms INTEGER,
            img_gen_ms INTEGER,
            started_at TEXT,
            input_album_photo_id TEXT,
            style TEXT
        )
    """)
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE runs ADD COLUMN style TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS styles (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL
        )
    """)
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute(
            "ALTER TABLE styles ADD COLUMN used_count INTEGER NOT NULL DEFAULT 0",
        )
    conn.executemany(
        "INSERT OR IGNORE INTO styles (name, description) VALUES (?, ?)",
        STYLES,
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def get_config(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM config WHERE key = ?",
        (key,),
    ).fetchone()
    return row[0] if row else None


def set_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def insert_run(conn: sqlite3.Connection, input_file_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO runs (input_file_path, started_at) VALUES (?, datetime('now'))",
        (input_file_path,),
    )
    conn.commit()
    if cur.lastrowid is None:
        msg = "INSERT did not return a row ID"
        raise RuntimeError(msg)
    return cur.lastrowid


def update_run(conn: sqlite3.Connection, run_id: int, **kwargs: str | float) -> None:
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    conn.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*kwargs.values(), run_id))
    conn.commit()


def avg_duration_ms(conn: sqlite3.Connection, column: str) -> float | None:
    row = conn.execute(
        f"SELECT AVG({column}) FROM runs WHERE {column} IS NOT NULL",
    ).fetchone()
    val = row[0] if row else None
    return float(val) if val is not None else None


def lookup_description(conn: sqlite3.Connection, input_file_path: str) -> str | None:
    row = conn.execute(
        "SELECT generated_description FROM runs "
        "WHERE input_file_path = ? AND generated_description IS NOT NULL LIMIT 1",
        (input_file_path,),
    ).fetchone()
    return row[0] if row else None


def get_recent_runs(
    conn: sqlite3.Connection,
    limit: int = 20,
) -> list[tuple[str | None, ...]]:
    """Return the most recent runs for display, newest first."""
    return conn.execute(
        "SELECT started_at, input_file_path, style, desc_gen_ms, img_gen_ms, output_image_path "
        "FROM runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def increment_style_count(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "UPDATE styles SET used_count = used_count + 1 WHERE name = ?", (name,),
    )
    conn.commit()


def random_style(conn: sqlite3.Connection) -> tuple[str, str] | tuple[None, None]:
    row = conn.execute(
        "SELECT name, description FROM styles ORDER BY RANDOM() LIMIT 1",
    ).fetchone()
    if row:
        return row[0], row[1]
    return None, None
