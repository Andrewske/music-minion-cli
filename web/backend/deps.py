from typing import AsyncGenerator
from music_minion.core.database import get_db_connection
from music_minion.core.config import load_config, Config


async def get_db() -> AsyncGenerator:
    """FastAPI dependency for database connections."""
    with get_db_connection() as conn:
        yield conn


def get_config() -> Config:
    """FastAPI dependency for configuration."""
    return load_config()
