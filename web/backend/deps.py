from contextlib import contextmanager
from typing import Generator
from music_minion.core.database import get_db_connection
from music_minion.core.config import load_config, Config


@contextmanager
def get_db() -> Generator:
    """FastAPI dependency for database connections."""
    with get_db_connection() as conn:
        yield conn


def get_config() -> Config:
    """FastAPI dependency for configuration."""
    return load_config()
