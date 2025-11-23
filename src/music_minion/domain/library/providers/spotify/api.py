"""
Spotify API operations.

Pure functions for library sync, playlists, playback control.
All functions take ProviderState and return (ProviderState, result).
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from loguru import logger

from music_minion.core import database
from music_minion.core.output import log

from ...provider import ProviderState

# Type aliases
TrackMetadata = Dict[str, Any]
TrackData = Tuple[str, TrackMetadata]
TrackList = List[TrackData]

# Spotify API base URL
API_BASE = "https://api.spotify.com/v1"


def _ensure_valid_token(
    state: ProviderState,
) -> Tuple[ProviderState, Optional[Dict[str, Any]]]:
    """Ensure access token is valid, refreshing if expired.

    This helper is called by EVERY API function to handle token refresh
    transparently. Pattern adopted from SoundCloud provider.

    Returns:
        (updated_state, token_data or None)
    """
    from . import auth

    token_data = state.cache.get("token_data")
    if not token_data:
        logger.debug("No token data in cache")
        return state, None

    # Token still valid
    if not auth.is_token_expired(token_data):
        return state, token_data

    # Attempt refresh
    logger.info("Spotify token expired, attempting refresh")
    new_token_data = auth.refresh_token(token_data)
    if new_token_data:
        auth._save_user_tokens(new_token_data)
        state = state.with_cache(token_data=new_token_data)
        logger.debug("Token refreshed successfully")
        return state, new_token_data
    else:
        # Refresh failed - mark as unauthenticated
        logger.warning("Token refresh failed, marking as unauthenticated")
        return state.with_authenticated(False), None


def _normalize_spotify_track(track: Dict[str, Any]) -> TrackMetadata:
    """Convert Spotify API track response to standard metadata format."""
    return {
        "title": track.get("name", "").strip(),
        "artist": ", ".join(
            [a["name"] for a in track.get("artists", []) if a.get("name") is not None]
        ),
        "top_level_artist": track.get("artists", [{}])[0].get("name", ""),
        "album": track.get("album", {}).get("name", ""),
        "year": (
            int(track["album"]["release_date"][:4])
            if track.get("album", {}).get("release_date")
            else None
        ),
        "duration": track.get("duration_ms", 0) / 1000.0
        if track.get("duration_ms")
        else None,
        "genre": None,  # Not in basic API response
        "bpm": None,  # Audio features API deprecated
        "key_signature": None,  # Audio features API deprecated
    }


def sync_library(
    state: ProviderState, incremental: bool = True
) -> Tuple[ProviderState, TrackList]:
    """Sync user's saved tracks from Spotify with optimized incremental sync.

    Optimization strategy:
    1. Check total liked count from first API call
    2. If count unchanged -> skip pagination entirely (97% reduction)
    3. If count changed -> use timestamp-based early exit

    Phase 1: Fetch new tracks (incremental with count check)
    Phase 2: Sync like markers (only if count changed)

    Args:
        state: Provider state
        incremental: If True, use count check and timestamp-based early exit

    Returns:
        (updated_state, track_list)
    """
    state, token = _ensure_valid_token(state)
    if not token:
        logger.warning("Cannot sync library - not authenticated")
        return state, []

    try:
        # Load existing track IDs for incremental check
        existing_ids: Set[str] = set()
        if incremental:
            with database.get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT spotify_id FROM tracks WHERE spotify_id IS NOT NULL"
                )
                existing_ids = {row[0] for row in cursor.fetchall()}
            logger.info(
                f"Incremental sync: {len(existing_ids)} existing Spotify tracks"
            )

        # Optimized fetch with count check and timestamp-based early exit
        tracks, all_liked_ids, new_state = _fetch_saved_tracks_optimized(
            token["access_token"], existing_ids, incremental, state
        )

        # Update state with new cache values
        state = new_state

        log(f"✓ Fetched {len(tracks)} new tracks from Spotify", level="info")
        logger.info(f"Collected {len(all_liked_ids)} liked track IDs for sync")

        # Sync like markers for collected liked tracks
        if all_liked_ids:
            placeholders = ",".join(["?" for _ in all_liked_ids])
            with database.get_db_connection() as conn:
                cursor = conn.execute(
                    f"SELECT id FROM tracks WHERE spotify_id IN ({placeholders})",
                    list(all_liked_ids),
                )
                db_track_ids = [row[0] for row in cursor.fetchall()]

            if db_track_ids:
                # Batch insert like markers
                likes_synced = database.batch_add_spotify_likes(db_track_ids)
                log(f"📊 Synced {likes_synced} Spotify like markers", level="info")
                logger.info(
                    f"Like markers synced: {likes_synced} for {len(db_track_ids)} tracks"
                )
            else:
                logger.debug("No database tracks found for like marker sync")

        return state, tracks

    except requests.HTTPError as e:
        if e.response.status_code == 429:
            logger.warning("Spotify rate limit hit during library sync")
            log("⚠ Rate limit reached, please try again later", level="warning")
            return state, []
        elif e.response.status_code == 401:
            logger.error("Authentication failed during library sync")
            log("❌ Authentication failed, please re-authenticate", level="error")
            return state.with_authenticated(False), []
        else:
            logger.exception(
                f"HTTP error during library sync: {e.response.status_code}"
            )
            log(f"❌ HTTP error: {e.response.status_code}", level="error")
            return state, []
    except Exception as e:
        logger.exception("Unexpected error during library sync")
        log(f"❌ Sync error: {e}", level="error")
        return state, []


def _fetch_saved_tracks_optimized(
    token: str, existing_ids: Set[str], incremental: bool, state: ProviderState
) -> Tuple[TrackList, Set[str], ProviderState]:
    """Fetch saved tracks with count check + timestamp-based early exit optimization.

    Optimization strategy:
    1. Fetch first page (includes total count)
    2. Compare with cached last_liked_count
    3. If equal -> skip pagination (no changes)
    4. If different -> use timestamp-based early exit

    Returns:
        tracks: New tracks to import (metadata)
        all_liked_ids: Liked track IDs for marker sync
        updated_state: State with new cache values
    """
    from datetime import datetime

    tracks = []
    all_liked_ids: Set[str] = set()
    url = f"{API_BASE}/me/tracks"
    params = {"limit": 50}
    headers = {"Authorization": f"Bearer {token}"}

    logger.debug("Fetching saved tracks from Spotify (optimized)")

    # Fetch first page to check total count
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    current_count = data.get("total", 0)
    cached_count = state.cache.get("last_liked_count")
    last_sync_timestamp = state.cache.get("last_like_sync_timestamp")

    logger.info(f"Current liked tracks: {current_count}, Cached: {cached_count}")

    # Count check optimization: if count unchanged, skip pagination
    if incremental and cached_count is not None and current_count == cached_count:
        logger.info("✓ Like count unchanged - skipping pagination (0 API calls)")
        log("✓ No new liked tracks detected", level="info")
        # Update state with current timestamp
        new_state = state.with_cache(
            last_liked_count=current_count,
            last_like_sync_timestamp=datetime.utcnow().isoformat(),
        )
        return [], set(), new_state

    logger.info(
        f"Like count changed ({cached_count} → {current_count}), fetching updates..."
    )

    # Process first page
    stop_pagination = False
    for item in data["items"]:
        if not item.get("track"):
            continue

        track_id = item["track"]["id"]
        added_at = item.get("added_at")  # ISO 8601 timestamp

        # Timestamp-based early exit
        if incremental and last_sync_timestamp and added_at:
            if added_at < last_sync_timestamp:
                logger.debug(
                    f"Reached tracks older than last sync ({added_at} < {last_sync_timestamp})"
                )
                stop_pagination = True
                break

        all_liked_ids.add(track_id)

        # Incremental: skip metadata if track exists
        if track_id not in existing_ids:
            metadata = _normalize_spotify_track(item["track"])
            tracks.append((track_id, metadata))

    # Continue pagination if needed
    url = data.get("next") if not stop_pagination else None
    params = {}  # URL contains all params

    while url:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        for item in data["items"]:
            if not item.get("track"):
                continue

            track_id = item["track"]["id"]
            added_at = item.get("added_at")

            # Timestamp-based early exit
            if incremental and last_sync_timestamp and added_at:
                if added_at < last_sync_timestamp:
                    logger.debug(
                        "Reached tracks older than last sync, stopping pagination"
                    )
                    url = None
                    break

            all_liked_ids.add(track_id)

            if track_id not in existing_ids:
                metadata = _normalize_spotify_track(item["track"])
                tracks.append((track_id, metadata))

        if url:
            url = data.get("next")

        # Progress logging every 50 tracks
        if len(tracks) % 50 == 0 and tracks:
            logger.debug(f"Fetched {len(tracks)} new tracks so far...")

    # Update state cache with new count and timestamp
    new_state = state.with_cache(
        last_liked_count=current_count,
        last_like_sync_timestamp=datetime.utcnow().isoformat(),
    )

    logger.info(
        f"Fetch complete: {len(tracks)} new tracks, {len(all_liked_ids)} liked IDs collected"
    )
    return tracks, all_liked_ids, new_state


def search(state: ProviderState, query: str) -> Tuple[ProviderState, TrackList]:
    """Search for tracks on Spotify.

    Args:
        state: Provider state
        query: Search query string

    Returns:
        (updated_state, track_list) - top 20 results
    """
    state, token = _ensure_valid_token(state)
    if not token:
        logger.warning("Cannot search - not authenticated")
        return state, []

    try:
        url = f"{API_BASE}/search"
        params = {
            "q": query,
            "type": "track",
            "limit": 20,
        }
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        tracks = []
        for track in data.get("tracks", {}).get("items", []):
            track_id = track["id"]
            metadata = _normalize_spotify_track(track)
            tracks.append((track_id, metadata))

        logger.info(f"Search found {len(tracks)} results for: {query}")
        return state, tracks

    except Exception as e:
        logger.exception(f"Error searching Spotify: {e}")
        return state, []


def like_track(
    state: ProviderState, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Save track to user's Spotify library.

    Args:
        state: Provider state
        track_id: Spotify track ID

    Returns:
        (updated_state, success, error_message)
    """
    state, token = _ensure_valid_token(state)
    if not token:
        return state, False, "Not authenticated"

    try:
        url = f"{API_BASE}/me/tracks"
        params = {"ids": track_id}
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        response = requests.put(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        logger.info(f"Liked track on Spotify: {track_id}")
        return state, True, None

    except requests.HTTPError as e:
        logger.exception(f"HTTP error liking track {track_id}")
        return state, False, f"HTTP error: {e.response.status_code}"
    except Exception as e:
        logger.exception(f"Error liking track {track_id}")
        return state, False, str(e)


def unlike_track(
    state: ProviderState, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Remove track from user's Spotify library.

    Args:
        state: Provider state
        track_id: Spotify track ID

    Returns:
        (updated_state, success, error_message)
    """
    state, token = _ensure_valid_token(state)
    if not token:
        return state, False, "Not authenticated"

    try:
        url = f"{API_BASE}/me/tracks"
        params = {"ids": track_id}
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        response = requests.delete(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        logger.info(f"Unliked track on Spotify: {track_id}")
        return state, True, None

    except requests.HTTPError as e:
        logger.exception(f"HTTP error unliking track {track_id}")
        return state, False, f"HTTP error: {e.response.status_code}"
    except Exception as e:
        logger.exception(f"Error unliking track {track_id}")
        return state, False, str(e)


def get_stream_url(state: ProviderState, spotify_id: str) -> Optional[str]:
    """Return Spotify URI for playback routing.

    Args:
        state: Provider state
        spotify_id: Spotify track ID

    Returns:
        spotify:track:{id} URI or None
    """
    return f"spotify:track:{spotify_id}"


# ==================== PLAYLIST FUNCTIONS ====================


def get_playlists(state: ProviderState, full: bool = False) -> Tuple[ProviderState, List[Dict[str, Any]]]:
    """Fetch user's playlists with snapshot_id change detection optimization.

    Optimization: Only fetches tracks for playlists with changed snapshot_id.
    This reduces API calls from 51 (1 + 50 playlists) to 1-6 typically (88-98% reduction).
    Can be bypassed with full=True to always fetch tracks.

    Args:
        state: Provider state
        full: If True, bypass snapshot_id optimization and fetch all tracks (default: False)

    Returns list of playlist dicts with structure:
    {
        "id": "playlist_id",
        "name": "Playlist Name",
        "track_count": N,
        "tracks": [(track_id, metadata), ...],  # Empty if snapshot_id unchanged
        "description": "...",
        "last_modified": "snapshot_id",
        "created_at": "ISO-8601 timestamp" or None  # Oldest track added_at (proxy for creation)
    }
    """
    state, token = _ensure_valid_token(state)
    if not token:
        logger.warning("Cannot fetch playlists - not authenticated")
        return state, []

    # Load stored snapshot_ids from database for change detection
    stored_snapshots = {}
    try:
        with database.get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT spotify_playlist_id, spotify_snapshot_id FROM playlists WHERE spotify_playlist_id IS NOT NULL"
            )
            stored_snapshots = {row[0]: row[1] for row in cursor.fetchall()}
        logger.debug(f"Loaded {len(stored_snapshots)} stored playlist snapshot_ids")
    except Exception as e:
        logger.warning(f"Could not load stored snapshots: {e}")
        # Continue without optimization if database error

    playlists = []
    url = f"{API_BASE}/me/playlists"
    params = {"limit": 50}
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    skipped_count = 0
    fetched_count = 0

    try:
        logger.debug("Fetching playlists from Spotify (optimized with snapshot_id)")

        while url:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data["items"]:
                playlist_id = item["id"]
                current_snapshot = item["snapshot_id"]
                stored_snapshot = stored_snapshots.get(playlist_id)

                # Optimization: Only fetch tracks if snapshot_id changed (unless full=True)
                if stored_snapshot and current_snapshot == stored_snapshot and not full:
                    # Playlist unchanged - return empty tracks list
                    tracks = []
                    created_at = None  # Will preserve existing DB value during sync
                    skipped_count += 1
                    logger.debug(
                        f"Skipping unchanged playlist: {item['name']} (snapshot: {current_snapshot})"
                    )
                else:
                    # Playlist changed or new - fetch tracks
                    state, tracks, created_at = get_playlist_tracks(state, playlist_id)
                    fetched_count += 1
                    if full:
                        logger.debug(
                            f"Fetching playlist (full sync): {item['name']} (snapshot: {current_snapshot})"
                        )
                    elif stored_snapshot:
                        logger.debug(
                            f"Fetching updated playlist: {item['name']} (snapshot: {stored_snapshot} → {current_snapshot})"
                        )
                    else:
                        logger.debug(
                            f"Fetching new playlist: {item['name']} (snapshot: {current_snapshot})"
                        )

                playlist_data = {
                    "id": playlist_id,
                    "name": item["name"],
                    "track_count": item["tracks"]["total"],
                    "tracks": tracks,
                    "description": item.get("description", ""),
                    "last_modified": current_snapshot,
                    "created_at": created_at,
                }
                playlists.append(playlist_data)

            url = data.get("next")
            params = {}

        log(
            f"✓ Fetched {len(playlists)} playlists ({fetched_count} updated, {skipped_count} unchanged)",
            level="info",
        )
        logger.info(
            f"Playlists fetch complete: {len(playlists)} total, {fetched_count} fetched, {skipped_count} skipped"
        )
        return state, playlists

    except Exception as e:
        logger.exception("Error fetching playlists")
        log(f"❌ Error fetching playlists: {e}", level="error")
        return state, []


def get_playlist_tracks(
    state: ProviderState, playlist_id: str
) -> Tuple[ProviderState, TrackList, Optional[str]]:
    """Fetch tracks for specific playlist.

    Args:
        state: Provider state
        playlist_id: Spotify playlist ID or URN (spotify:playlists:{id})

    Returns:
        (updated_state, track_list, oldest_added_at_timestamp)
        oldest_added_at_timestamp is ISO 8601 string or None if no tracks
    """
    state, token = _ensure_valid_token(state)
    if not token:
        return state, [], None

    # Handle URN format: spotify:playlists:{id}
    if ":" in playlist_id:
        playlist_id = playlist_id.split(":")[-1]

    tracks = []
    oldest_added_at = None
    url = f"{API_BASE}/playlists/{playlist_id}"
    params = {"limit": 100}
    headers = {"Authorization": f"Bearer {token['access_token']}"}

    try:
        while url:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data["tracks"]["items"]:
                if not item.get("track"):  # Skip local files and removed tracks
                    continue
                if item["track"].get("is_local"):  # Skip local files
                    continue

                track_id = item["track"]["id"]
                metadata = _normalize_spotify_track(item["track"])
                tracks.append((track_id, metadata))

                # Track oldest added_at timestamp (proxy for playlist creation date)
                added_at = item.get("added_at")
                if added_at:
                    if oldest_added_at is None or added_at < oldest_added_at:
                        oldest_added_at = added_at

            url = data.get("next")
            params = {}

        logger.debug(f"Fetched {len(tracks)} tracks for playlist {playlist_id}, oldest track: {oldest_added_at}")
        return state, tracks, oldest_added_at

    except Exception:
        logger.exception(f"Error fetching playlist tracks: {playlist_id}")
        return state, [], None


def create_playlist(
    state: ProviderState, name: str, description: str = ""
) -> Tuple[ProviderState, Optional[str], Optional[str]]:
    """Create new Spotify playlist.

    Args:
        state: Provider state
        name: Playlist name
        description: Optional playlist description

    Returns:
        (updated_state, playlist_id or None, error_message or None)
    """
    state, token = _ensure_valid_token(state)
    if not token:
        return state, None, "Not authenticated"

    try:
        # Get user ID first
        user_response = requests.get(
            f"{API_BASE}/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        user_response.raise_for_status()
        user_id = user_response.json()["id"]

        # Create playlist
        url = f"{API_BASE}/users/{user_id}/playlists"
        payload = {"name": name, "description": description, "public": False}
        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()

        playlist_id = response.json()["id"]
        logger.info(f"Created Spotify playlist: {name} ({playlist_id})")
        log(f"✓ Created playlist: {name}", level="info")
        return state, playlist_id, None

    except Exception as e:
        logger.exception(f"Error creating playlist: {name}")
        return state, None, str(e)


def add_track_to_playlist(
    state: ProviderState, playlist_id: str, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Add track to Spotify playlist.

    Args:
        state: Provider state
        playlist_id: Spotify playlist ID or URN
        track_id: Spotify track ID or URN

    Returns:
        (updated_state, success, error_message)
    """
    state, token = _ensure_valid_token(state)
    if not token:
        return state, False, "Not authenticated"

    # Handle URN formats
    if ":" in playlist_id:
        playlist_id = playlist_id.split(":")[-1]
    if ":" in track_id:
        track_id = track_id.split(":")[-1]

    try:
        url = f"{API_BASE}/playlists/{playlist_id}/tracks"
        payload = {"uris": [f"spotify:track:{track_id}"]}
        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()

        logger.info(f"Added track {track_id} to playlist {playlist_id}")
        return state, True, None

    except Exception as e:
        logger.exception(f"Error adding track to playlist: {playlist_id}")
        return state, False, str(e)


def remove_track_from_playlist(
    state: ProviderState, playlist_id: str, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Remove track from Spotify playlist.

    Args:
        state: Provider state
        playlist_id: Spotify playlist ID or URN
        track_id: Spotify track ID or URN

    Returns:
        (updated_state, success, error_message)
    """
    state, token = _ensure_valid_token(state)
    if not token:
        return state, False, "Not authenticated"

    # Handle URN formats
    if ":" in playlist_id:
        playlist_id = playlist_id.split(":")[-1]
    if ":" in track_id:
        track_id = track_id.split(":")[-1]

    try:
        url = f"{API_BASE}/playlists/{playlist_id}/tracks"
        payload = {"tracks": [{"uri": f"spotify:track:{track_id}"}]}
        response = requests.delete(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()

        logger.info(f"Removed track {track_id} from playlist {playlist_id}")
        return state, True, None

    except Exception as e:
        logger.exception(f"Error removing track from playlist: {playlist_id}")
        return state, False, str(e)


# ==================== INTERNAL PLAYBACK FUNCTIONS ====================


def _spotify_play(
    state: ProviderState, track_id: str, device_id: Optional[str]
) -> bool:
    """Internal: Start playback on device.

    Called by SpotifyPlayer class.
    """
    state, token = _ensure_valid_token(state)
    if not token:
        logger.warning("Cannot play - not authenticated")
        return False

    try:
        url = f"{API_BASE}/me/player/play"
        if device_id:
            url += f"?device_id={device_id}"

        payload = {"uris": [f"spotify:track:{track_id}"]}
        response = requests.put(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()
        logger.debug(f"Started playback: {track_id}")
        return True

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.error("No active Spotify device found")
            log(
                "❌ No Spotify device available. Open Spotify on a device first.",
                level="error",
            )
        else:
            logger.exception(f"Error starting playback: {e.response.status_code}")
        return False
    except Exception:
        logger.exception("Error starting playback")
        return False


def _spotify_pause(state: ProviderState) -> bool:
    """Internal: Pause playback."""
    state, token = _ensure_valid_token(state)
    if not token:
        return False

    try:
        response = requests.put(
            f"{API_BASE}/me/player/pause",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()
        logger.debug("Paused Spotify playback")
        return True
    except Exception:
        logger.exception("Error pausing playback")
        return False


def _spotify_resume(state: ProviderState) -> bool:
    """Internal: Resume playback."""
    state, token = _ensure_valid_token(state)
    if not token:
        return False

    try:
        response = requests.put(
            f"{API_BASE}/me/player/play",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()
        logger.debug("Resumed Spotify playback")
        return True
    except Exception:
        logger.exception("Error resuming playback")
        return False


def _spotify_get_current_playback(state: ProviderState) -> Optional[Dict[str, Any]]:
    """Internal: Get current playback state."""
    state, token = _ensure_valid_token(state)
    if not token:
        return None

    try:
        response = requests.get(
            f"{API_BASE}/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        if response.status_code == 204:  # No content = nothing playing
            return None
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.debug(f"Error getting playback state: {e}")
        return None


def _spotify_seek(state: ProviderState, position_ms: int) -> bool:
    """Internal: Seek to position."""
    state, token = _ensure_valid_token(state)
    if not token:
        return False

    try:
        response = requests.put(
            f"{API_BASE}/me/player/seek?position_ms={position_ms}",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()
        logger.debug(f"Seeked to position: {position_ms}ms")
        return True
    except Exception:
        logger.exception("Error seeking")
        return False


def _spotify_get_devices(state: ProviderState) -> List[Dict[str, Any]]:
    """Internal: Get available Spotify devices."""
    state, token = _ensure_valid_token(state)
    if not token:
        return []

    try:
        response = requests.get(
            f"{API_BASE}/me/player/devices",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=30,
        )
        response.raise_for_status()
        devices = response.json().get("devices", [])
        logger.debug(f"Found {len(devices)} Spotify devices")
        return devices
    except Exception:
        logger.exception("Error getting devices")
        return []
