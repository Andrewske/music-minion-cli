from contextlib import contextmanager
from typing import Generator
from music_minion.core.database import get_db_connection


@contextmanager
def get_db() -> Generator:
    """FastAPI dependency for database connections."""
    with get_db_connection() as conn:
        yield conn
