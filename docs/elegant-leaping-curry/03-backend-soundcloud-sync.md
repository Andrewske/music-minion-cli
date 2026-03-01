---
task: 03-backend-soundcloud-sync
status: done
depends:
  - 01-database-migration
files:
  - path: src/music_minion/domain/library/providers/base.py
    action: create
  - path: scripts/preseed_soundcloud_likes.py
    action: create
  - path: web/backend/routers/soundcloud.py
    action: modify
---

# Backend: SoundCloud Library Sync Endpoint

## Context

Users need a way to sync their SoundCloud library (likes + playlists) to the local database as separate track records with `source='soundcloud'`. These tracks can then be browsed and streamed from the SoundCloud library view.

**Key optimization:** Preseed likes from `~/coding/soundcloud-discovery/.cache/likes.parquet` (6731 cached likes), then delta sync only fetches new likes.

## Files to Modify/Create

- `src/music_minion/domain/library/providers/base.py` (new - Provider interface)
- `scripts/preseed_soundcloud_likes.py` (new - one-time import script)
- `web/backend/routers/soundcloud.py` (modify)

## Part 1: Provider Interface (for future Spotify support)

Create a thin provider abstraction that both SoundCloud and future Spotify can implement:

```python
# src/music_minion/domain/library/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProviderTrack:
    """Normalized track from any provider."""
    provider_id: str  # soundcloud_id, spotify_id, etc.
    title: str
    artist: str
    genre: Optional[str] = None
    bpm: Optional[float] = None
    duration: Optional[float] = None  # seconds
    source_url: Optional[str] = None  # permalink for streaming

@dataclass
class ProviderPlaylist:
    """Normalized playlist from any provider."""
    provider_id: str
    name: str
    track_count: int

class Provider(ABC):
    """Base interface for music providers (SoundCloud, Spotify, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for database source column."""
        ...

    @abstractmethod
    def get_stream_url(self, provider_id: str) -> Optional[str]:
        """Get playable stream URL for a track."""
        ...

    @abstractmethod
    def get_playlists(self) -> list[ProviderPlaylist]:
        """Get user's playlists."""
        ...

    @abstractmethod
    def get_playlist_tracks(self, playlist_id: str) -> list[ProviderTrack]:
        """Get tracks in a playlist."""
        ...

    @abstractmethod
    def get_liked_tracks(self, since_timestamp: Optional[str] = None) -> list[ProviderTrack]:
        """Get user's liked tracks, optionally since a timestamp for delta sync."""
        ...
```

## Part 2: Preseed Script

One-time script to import cached likes from soundcloud-discovery:

```python
# scripts/preseed_soundcloud_likes.py
"""Preseed SoundCloud likes from soundcloud-discovery cache.

Usage: uv run python scripts/preseed_soundcloud_likes.py
"""
import pandas as pd
from pathlib import Path
from music_minion.core.database import get_db_connection

LIKES_PARQUET = Path.home() / "coding/soundcloud-discovery/.cache/likes.parquet"

def preseed_likes():
    if not LIKES_PARQUET.exists():
        print(f"Cache not found: {LIKES_PARQUET}")
        return

    df = pd.read_parquet(LIKES_PARQUET)
    print(f"Found {len(df)} cached likes")

    with get_db_connection() as conn:
        inserted = 0
        for _, row in df.iterrows():
            # Use metadata_artist if available, fall back to artist_name
            artist = row.get('metadata_artist') or row.get('artist_name') or ''

            conn.execute("""
                INSERT INTO tracks (
                    title, artist, genre, source, soundcloud_id, source_url
                ) VALUES (?, ?, ?, 'soundcloud', ?, ?)
                ON CONFLICT (source, soundcloud_id) DO UPDATE SET
                    title = excluded.title,
                    artist = excluded.artist,
                    genre = excluded.genre
            """, (
                row['title'],
                artist,
                row.get('genre'),
                str(row['track_id']),
                f"https://soundcloud.com/{row['track_slug']}",
            ))
            inserted += 1

        # Create "SoundCloud Likes" playlist
        conn.execute("""
            INSERT INTO playlists (name, library, track_count, type)
            VALUES ('SoundCloud Likes', 'soundcloud', ?, 'manual')
            ON CONFLICT (name, library) DO UPDATE SET track_count = excluded.track_count
        """, (len(df),))

        # Get playlist ID
        cursor = conn.execute(
            "SELECT id FROM playlists WHERE name = 'SoundCloud Likes' AND library = 'soundcloud'"
        )
        playlist_id = cursor.fetchone()[0]

        # Link tracks to playlist
        cursor = conn.execute(
            "SELECT id, soundcloud_id FROM tracks WHERE source = 'soundcloud'"
        )
        id_map = {row['soundcloud_id']: row['id'] for row in cursor.fetchall()}

        conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))

        playlist_tracks = []
        for idx, (_, row) in enumerate(df.iterrows()):
            sc_id = str(row['track_id'])
            if sc_id in id_map:
                playlist_tracks.append((playlist_id, id_map[sc_id], idx + 1))

        conn.executemany(
            "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
            playlist_tracks
        )

        conn.commit()
        print(f"Inserted {inserted} tracks, linked {len(playlist_tracks)} to playlist")

if __name__ == "__main__":
    preseed_likes()
```

## Part 3: Delta Sync Endpoint

## Part 3: Delta Sync Endpoint

Add endpoint for incremental sync (only fetches new likes since last sync):

```python
from pydantic import BaseModel
from loguru import logger

class SyncResponse(BaseModel):
    tracks_synced: int
    playlists_synced: int
    likes_synced: int
    errors: list[str]

@router.post("/soundcloud/sync")
async def sync_soundcloud_library(db=Depends(get_db)) -> SyncResponse:
    """
    Sync SoundCloud library to local database.
    Creates track records with source='soundcloud' that can be streamed.
    Creates playlists with library='soundcloud'.
    Creates special "SoundCloud Likes" playlist with all liked tracks.
    """
    from music_minion.domain.library.providers.soundcloud.api import (
        get_playlists,
        get_playlist_tracks,
        _fetch_user_likes_with_markers,
    )
    from web.backend.soundcloud_auth import get_web_provider_state

    # Get authenticated state
    state = get_web_provider_state()
    if not state or not state.authenticated:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

    token_data = state.cache.get("token_data")
    if not token_data:
        raise HTTPException(status_code=401, detail="SoundCloud token not found")

    access_token = token_data["access_token"]

    errors = []
    tracks_synced = 0
    playlists_synced = 0
    likes_synced = 0

    try:
        # =====================
        # 1. Sync user playlists
        # =====================
        # NOTE: These are SYNCHRONOUS functions - no await!
        updated_state, sc_playlists = get_playlists(state)

        for sc_playlist in sc_playlists:
            try:
                # Fetch tracks for playlist (synchronous)
                updated_state, sc_tracks, _ = get_playlist_tracks(updated_state, sc_playlist['id'])

                # Upsert tracks with source='soundcloud' and FULL metadata
                for sc_id, metadata in sc_tracks:
                    db.execute("""
                        INSERT INTO tracks (
                            title, artist, genre, bpm, duration,
                            source, soundcloud_id, source_url
                        ) VALUES (?, ?, ?, ?, ?, 'soundcloud', ?, ?)
                        ON CONFLICT (source, soundcloud_id)
                        DO UPDATE SET
                            title = excluded.title,
                            artist = excluded.artist,
                            genre = excluded.genre,
                            bpm = excluded.bpm,
                            duration = excluded.duration,
                            source_url = excluded.source_url
                    """, (
                        metadata.get('title'),
                        metadata.get('artist'),
                        metadata.get('genre'),
                        metadata.get('bpm'),
                        metadata.get('duration'),
                        sc_id,
                        f"https://soundcloud.com/tracks/{sc_id}",  # Permalink for yt-dlp fallback
                    ))
                    tracks_synced += 1

                # Create/update playlist
                cursor = db.execute("""
                    INSERT INTO playlists (
                        name, library, soundcloud_playlist_id, track_count, type
                    ) VALUES (?, 'soundcloud', ?, ?, 'manual')
                    ON CONFLICT (soundcloud_playlist_id, library)
                    DO UPDATE SET
                        name = excluded.name,
                        track_count = excluded.track_count
                    RETURNING id
                """, (
                    sc_playlist['name'],
                    sc_playlist['id'],
                    len(sc_tracks),
                ))
                playlist_id = cursor.fetchone()[0]

                # Link tracks to playlist via playlist_tracks
                # First, get track IDs for the SC tracks we just upserted
                sc_ids = [sc_id for sc_id, _ in sc_tracks]
                placeholders = ','.join('?' * len(sc_ids))
                cursor = db.execute(
                    f"SELECT id, soundcloud_id FROM tracks WHERE soundcloud_id IN ({placeholders}) AND source = 'soundcloud'",
                    sc_ids
                )
                id_map = {row['soundcloud_id']: row['id'] for row in cursor.fetchall()}

                # Clear existing playlist_tracks and re-insert with correct order
                db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
                playlist_track_rows = [
                    (playlist_id, id_map[sc_id], idx + 1)
                    for idx, (sc_id, _) in enumerate(sc_tracks)
                    if sc_id in id_map
                ]
                db.executemany(
                    "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                    playlist_track_rows
                )

                playlists_synced += 1
                logger.info(f"Synced playlist '{sc_playlist['name']}' with {len(sc_tracks)} tracks")

            except Exception as e:
                logger.exception(f"Failed to sync playlist {sc_playlist['name']}")
                errors.append(f"Failed to sync playlist {sc_playlist['name']}: {e}")

        # =====================
        # 2. Delta sync likes (only new since last sync)
        # =====================
        try:
            # Get most recent liked_at from existing SC tracks
            cursor = db.execute("""
                SELECT MAX(liked_at) FROM tracks WHERE source = 'soundcloud'
            """)
            last_sync = cursor.fetchone()[0]
            logger.info(f"Delta sync likes since: {last_sync or 'beginning'}")

            # Fetch only new likes (incremental=True stops at first existing track)
            liked_tracks, all_liked_ids = _fetch_user_likes_with_markers(
                access_token, existing_ids=set(), incremental=True
            )

            # Upsert liked tracks
            for sc_id, metadata in liked_tracks:
                db.execute("""
                    INSERT INTO tracks (
                        title, artist, genre, bpm, duration,
                        source, soundcloud_id, source_url
                    ) VALUES (?, ?, ?, ?, ?, 'soundcloud', ?, ?)
                    ON CONFLICT (source, soundcloud_id)
                    DO UPDATE SET
                        title = excluded.title,
                        artist = excluded.artist,
                        genre = excluded.genre,
                        bpm = excluded.bpm,
                        duration = excluded.duration,
                        source_url = excluded.source_url
                """, (
                    metadata.get('title'),
                    metadata.get('artist'),
                    metadata.get('genre'),
                    metadata.get('bpm'),
                    metadata.get('duration'),
                    sc_id,
                    f"https://soundcloud.com/tracks/{sc_id}",
                ))
                likes_synced += 1

            # Create/update "SoundCloud Likes" playlist
            cursor = db.execute("""
                INSERT INTO playlists (
                    name, library, track_count, type
                ) VALUES ('SoundCloud Likes', 'soundcloud', ?, 'manual')
                ON CONFLICT (name, library) WHERE name = 'SoundCloud Likes'
                DO UPDATE SET track_count = excluded.track_count
                RETURNING id
            """, (len(liked_tracks),))
            likes_playlist_id = cursor.fetchone()[0]

            # Link liked tracks
            sc_ids = [sc_id for sc_id, _ in liked_tracks]
            if sc_ids:
                placeholders = ','.join('?' * len(sc_ids))
                cursor = db.execute(
                    f"SELECT id, soundcloud_id FROM tracks WHERE soundcloud_id IN ({placeholders}) AND source = 'soundcloud'",
                    sc_ids
                )
                id_map = {row['soundcloud_id']: row['id'] for row in cursor.fetchall()}

                db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (likes_playlist_id,))
                playlist_track_rows = [
                    (likes_playlist_id, id_map[sc_id], idx + 1)
                    for idx, (sc_id, _) in enumerate(liked_tracks)
                    if sc_id in id_map
                ]
                db.executemany(
                    "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                    playlist_track_rows
                )

            playlists_synced += 1
            logger.info(f"Synced 'SoundCloud Likes' with {len(liked_tracks)} tracks")

        except Exception as e:
            logger.exception("Failed to sync likes")
            errors.append(f"Failed to sync likes: {e}")

        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception("Sync failed")
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")

    return SyncResponse(
        tracks_synced=tracks_synced,
        playlists_synced=playlists_synced,
        likes_synced=likes_synced,
        errors=errors,
    )
```

**Key design decisions:**
1. **Provider interface** - Thin abstraction for future Spotify support
2. **Preseed + delta** - Import 6731 cached likes once, then only fetch new likes
3. **No `await`** - SC API functions are synchronous, return `(state, data)` tuples
4. **Full metadata** - Includes genre, bpm, duration from `_normalize_soundcloud_track()`
5. **playlist_tracks populated** - Links tracks to playlists via batch insert
6. **Incremental sync** - Uses `incremental=True` to stop at first existing track

## Verification

1. Authenticate with SoundCloud first (`library auth soundcloud`)
2. Call sync endpoint:
   ```bash
   curl -X POST "http://localhost:8642/api/soundcloud/sync"
   ```
3. Verify tracks created with `source='soundcloud'`:
   ```sql
   SELECT COUNT(*) FROM tracks WHERE source = 'soundcloud';
   ```
4. Verify playlists created with `library='soundcloud'`:
   ```sql
   SELECT * FROM playlists WHERE library = 'soundcloud';
   ```
