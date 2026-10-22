"""Root pytest configuration: isolate every test from the real user data.

The app resolves its database, config and caches from XDG_DATA_HOME,
XDG_CONFIG_HOME and HOME. Env vars are pointed at a throwaway directory at
import time (before any test module imports app code that touches disk), and
each test then gets its own fresh, fully migrated SQLite database.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_SESSION_ROOT = Path(tempfile.mkdtemp(prefix="music-minion-tests-"))


def _isolated_env(root: Path) -> dict[str, str]:
    """Env vars that redirect every app path into ``root``."""
    return {
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "HOME": str(root / "home"),
        # Empty (not unset) so a later load_dotenv() can't inject a real URL
        "DATABASE_URL": "",
        # Tests own their throwaway DB; the real one is only owned by the pi
        "MUSIC_MINION_DB_OWNER": "1",
        "MUSIC_MINION_DB_PATH": "",
    }


_NON_PATH_KEYS = {"DATABASE_URL", "MUSIC_MINION_DB_OWNER", "MUSIC_MINION_DB_PATH"}


def _apply_env(env: dict[str, str]) -> None:
    for key, value in env.items():
        os.environ[key] = value
        if key not in _NON_PATH_KEYS:
            Path(value).mkdir(parents=True, exist_ok=True)


# Applied at conftest import so module-level code in app/test modules is safe.
_apply_env(_isolated_env(_SESSION_ROOT))


def _build_template_db() -> Path:
    """Create one migrated database to copy into each test."""
    from music_minion.core.database import get_database_path, init_database

    init_database()
    return get_database_path()


_TEMPLATE_DB = _build_template_db()


@pytest.fixture(autouse=True)
def isolated_data_dirs(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """Point the app at a per-test data dir holding a fresh migrated DB."""
    root = tmp_path_factory.mktemp("mm-home")
    for key, value in _isolated_env(root).items():
        monkeypatch.setenv(key, value)
        if key != "DATABASE_URL":
            Path(value).mkdir(parents=True, exist_ok=True)

    import music_minion.core.config as config_module
    from music_minion.core.database import get_database_path

    # Module-level cache of the 'All' playlist id would leak across test DBs
    monkeypatch.setattr(config_module, "ALL_PLAYLIST_ID", None)
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_TEMPLATE_DB, db_path)
    yield root


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    shutil.rmtree(_SESSION_ROOT, ignore_errors=True)
