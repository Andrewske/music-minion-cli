#!/usr/bin/env python3
"""Re-resolve a SoundCloud track whose original ID is dead (404/410 upstream).

Use case: track was removed from SC, then re-uploaded under a new ID with the
same slug URL. Resolve the slug URL via /resolve, update tracks.soundcloud_id
+ source_url, clear unavailable_at.

Usage:
    uv run scripts/reresolve_dead_sc_track.py <track_id> <soundcloud_url>

Example:
    uv run scripts/reresolve_dead_sc_track.py 26159 https://soundcloud.com/fabianmazur/killa
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import requests
from loguru import logger

from music_minion.core import database
from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud.api import (
    API_BASE_URL,
    _ensure_valid_token,
)


def load_provider_state() -> ProviderState:
    """Build ProviderState from on-disk SC user tokens (mirrors web backend loader)."""
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) / "music-minion" if data_home else Path.home() / ".local" / "share" / "music-minion"
    token_path = base / "soundcloud" / "user_tokens.json"
    if not token_path.exists():
        raise RuntimeError(f"No SC tokens at {token_path} - run `music-minion sc login`")
    token_data = json.loads(token_path.read_text())
    return ProviderState(
        config=ProviderConfig(name="soundcloud"),
        authenticated=True,
        cache={"token_data": token_data},
    )


def resolve_track_url(state: ProviderState, url: str) -> dict:
    """Hit SC /resolve to convert a track URL to track JSON."""
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        raise RuntimeError("Failed to refresh SC token")

    response = requests.get(
        f"{API_BASE_URL}/resolve",
        params={"url": url},
        headers={"Authorization": f"OAuth {token_data['access_token']}"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    track_id = int(sys.argv[1])
    sc_url = sys.argv[2]

    database.init_database()
    state = load_provider_state()

    logger.info(f"Resolving {sc_url} via SC /resolve...")
    track_data = resolve_track_url(state, sc_url)

    if track_data.get("kind") != "track":
        logger.error(f"URL did not resolve to a track (kind={track_data.get('kind')})")
        return 1

    new_sc_id = str(track_data["id"])
    title = track_data.get("title")
    artist = track_data.get("user", {}).get("username")
    logger.info(f"Resolved → id={new_sc_id} title={title!r} artist={artist!r}")

    with database.get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, title, artist, soundcloud_id FROM tracks WHERE id = ?",
            (track_id,),
        )
        row = cursor.fetchone()
        if not row:
            logger.error(f"Track {track_id} not found in DB")
            return 1
        logger.info(
            f"Current row: id={row['id']} title={row['title']!r} "
            f"artist={row['artist']!r} sc_id={row['soundcloud_id']}"
        )

        conn.execute(
            "UPDATE tracks SET soundcloud_id = ?, source_url = ?,"
            " unavailable_at = NULL, unavailable_reason = NULL,"
            " updated_at = CURRENT_TIMESTAMP"
            " WHERE id = ?",
            (new_sc_id, f"https://soundcloud.com/tracks/{new_sc_id}", track_id),
        )
        conn.commit()

    logger.info(f"✓ Track {track_id} updated: sc_id {row['soundcloud_id']} → {new_sc_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
