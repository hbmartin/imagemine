import sqlite3
from collections.abc import Generator

import pytest

from imagemine._db import init_db, set_config


@pytest.fixture
def conn() -> Generator[sqlite3.Connection]:
    c = init_db(":memory:")
    yield c
    c.close()


@pytest.fixture
def launchd_conn() -> Generator[sqlite3.Connection]:
    c = init_db(":memory:")
    for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "INPUT_ALBUM"):
        set_config(c, key, f"{key.lower()}-value")
    yield c
    c.close()
