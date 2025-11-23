"""
SoundCloud API operations.

Handles library sync, playlists, likes, and stream URLs.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger
from requests.exceptions import HTTPError

from music_minion.core.output import log

from ...provider import ProviderState, TrackList
from . import auth
from .auth import TOKEN_URL

# SoundCloud API base URL
API_BASE_URL = "https://api.soundcloud.com"


def _ensure_valid_token(
    state: ProviderState,
) -> Tuple[ProviderState, Optional[Dict[str, Any]]]:
    """Ensure access token is valid, refreshing if expired.

    Handles token expiry check and automatic refresh. Returns None if
    token cannot be refreshed, triggering re-authentication.

    Args:
        state: Current provider state

    Returns:
        (updated_state, token_data or None)
        - token_data is None if refresh failed (requires re-auth)
    """
    token_data = state.cache.get("token_data")
    if not token_data:
        return state, None

    if not auth.is_token_expired(token_data):
        return state, token_data

    # Token expired - attempt refresh
    new_token_data = auth.refresh_token(token_data)
    if new_token_data:
        auth._save_user_tokens(new_token_data)
        state = state.with_cache(token_data=new_token_data)
        return state, new_token_data
    else:
        # Refresh failed - mark as unauthenticated
        return state.with_authenticated(False), None


def _format_track_urn(track_id: str) -> str:
    """Format track ID as SoundCloud URN.

    Args:
        track_id: Numeric track ID or URN

    Returns:
        Track URN in format 'soundcloud:tracks:{id}'
    """
    # If already a URN, return as-is
    if track_id.startswith("soundcloud:tracks:"):
        return track_id
    # Otherwise, format as URN
    return f"soundcloud:tracks:{track_id}"


def _format_playlist_urn(playlist_id: str) -> str:
    """Format playlist ID as SoundCloud URN.

    Args:
        playlist_id: Numeric playlist ID or URN

    Returns:
        Playlist URN in format 'soundcloud:playlists:{id}'
    """
    # If already a URN, return as-is
    if playlist_id.startswith("soundcloud:playlists:"):
        return playlist_id
    # Otherwise, format as URN
    return f"soundcloud:playlists:{playlist_id}"


def sync_library(
    state: ProviderState, incremental: bool = True
) -> Tuple[ProviderState, TrackList]:
    """Sync SoundCloud likes/playlists and like markers.

    Performs incremental sync by default - only fetches new likes since last sync.
    Stops when encountering a track that's already been imported.

    Also syncs like markers for ALL tracks that are liked on SoundCloud,
    including tracks that were imported in previous syncs.

    Args:
        state: Current provider state
        incremental: If True, stop at first existing track; if False, fetch all (default: True)

    Returns:
        (new_state, [(track_id, metadata), ...])
    """
    if not state.authenticated:
        return state, []

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, []

    access_token = token_data["access_token"]

    # Get existing SoundCloud IDs for incremental sync
    from music_minion.core import database

    existing_ids = set()
    try:
        with database.get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT soundcloud_id FROM tracks WHERE soundcloud_id IS NOT NULL AND source = 'soundcloud'"
            )
            existing_ids = {row[0] for row in cursor.fetchall()}
        logger.info(
            f"Found {len(existing_ids)} existing SoundCloud tracks for incremental sync"
        )
    except Exception as e:
        logger.warning(f"Failed to load existing SoundCloud IDs: {e}")
        # Continue with full sync if we can't load existing tracks
        pass

    # Fetch user's likes (with progress reporting)
    logger.info("Starting SoundCloud likes sync")
    log("\n🔄 Syncing SoundCloud likes...", level="info")
    try:
        tracks, all_liked_ids = _fetch_user_likes_with_markers(
            access_token, existing_ids=existing_ids, incremental=incremental
        )
        logger.info(
            f"Fetched {len(tracks)} new tracks, {len(all_liked_ids)} total liked tracks"
        )
    except HTTPError as e:
        # Authentication failures - mark state as unauthenticated
        if e.response.status_code in (401, 403):
            from dataclasses import replace
            state = replace(state, authenticated=False)
            return state, []
        else:
            # Other HTTP errors - log and return empty
            logger.error(f"HTTP error syncing library: {e}")
            return state, []

    # Sync like markers for all matched tracks (both new and existing)
    likes_synced = 0
    try:
        if all_liked_ids:
            log(
                f"📊 Syncing like markers for {len(all_liked_ids)} liked tracks...",
                level="info",
            )
            logger.debug(
                f"Syncing like markers for {len(all_liked_ids)} SoundCloud tracks"
            )

            # Get track IDs from database for all soundcloud tracks that are liked
            with database.get_db_connection() as conn:
                # Build query with proper parameterization
                placeholders = ",".join("?" * len(all_liked_ids))
                cursor = conn.execute(
                    f"""
                    SELECT id FROM tracks
                    WHERE soundcloud_id IN ({placeholders})
                    """,
                    list(all_liked_ids),
                )
                db_track_ids = [row[0] for row in cursor.fetchall()]

            # Batch insert like markers (uses INSERT OR IGNORE to avoid duplicates)
            if db_track_ids:
                likes_synced = database.batch_add_soundcloud_likes(db_track_ids)
                logger.info(f"Synced {likes_synced} like markers to database")
                # Show combined status: likes synced + new tracks imported
                new_tracks_msg = f"{len(tracks)} new" if tracks else "no new"
                log(
                    f"✓ Synced {likes_synced} like markers ({new_tracks_msg} tracks to import)",
                    level="info",
                )
    except Exception as e:
        logger.error(f"Error syncing like markers: {e}", exc_info=True)
        log(f"⚠ Error syncing like markers: {e}", level="warning")
        log("  Check logs for details", level="info")

    new_state = state.with_sync_time()
    return new_state, tracks


def search(
    state: ProviderState,
    query: str,
) -> Tuple[ProviderState, TrackList]:
    """Search SoundCloud tracks.

    Args:
        state: Current provider state
        query: Search query

    Returns:
        (state, [(track_id, metadata), ...])
    """
    # Use client credentials for public search
    try:
        token = state.cache.get("token_data", {}).get("access_token")
        if not token:
            token = _get_client_credentials_token()
    except Exception:
        print("⚠ SoundCloud client credentials not configured")
        log("⚠ SoundCloud client credentials not configured", level="warning")

    # Search API
    url = f"{API_BASE_URL}/tracks"
    params = {
        "q": query,
        "limit": 50,
        "access": "[playable, preview, blocked]",  # Include all dates
    }

    headers = {"Authorization": f"OAuth {token}"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)

        response.raise_for_status()
        data = response.json()

        # for item in data:
        #     artist = (
        #         item.get("metadata_artist") or item.get("user", {}).get("username", "")
        #     ).strip()
        #     print(item["title"], artist, item.get("duration"))

        tracks = []
        for track in data:
            track_id = str(track["id"])
            metadata = _normalize_soundcloud_track(track)
            tracks.append((track_id, metadata))

        return state, tracks
    except Exception as exc:
        print("exception", exc)
        return state, []


def get_stream_url(state: ProviderState, provider_id: str) -> Optional[str]:
    """Get SoundCloud stream URL.

    Args:
        state: Current provider state
        provider_id: SoundCloud track ID

    Returns:
        Stream URL or None
    """
    if not state.authenticated:
        return None

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return None

    access_token = token_data["access_token"]

    # SoundCloud stream URL
    # MPV will follow the redirect to the actual progressive HTTP stream
    return f"{API_BASE_URL}/tracks/{provider_id}/stream?oauth_token={access_token}"


def get_playlists(state: ProviderState) -> Tuple[ProviderState, List[Dict[str, Any]]]:
    """Get user's SoundCloud playlists metadata (optimized for incremental sync).

    Args:
        state: Current provider state

    Returns:
        (state, [{"id": "...", "name": "...", "track_count": N, "last_modified": "..."}, ...])

    Note:
        Returns playlist metadata only. Tracks should be fetched separately using
        get_playlist_tracks() for playlists that need syncing (determined by last_modified).
        This avoids downloading thousands of track objects that won't be used.
    """
    if not state.authenticated:
        return state, []

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, []

    access_token = token_data["access_token"]

    # Fetch user's playlists metadata only (tracks fetched lazily as needed)
    url = f"{API_BASE_URL}/me/playlists"
    headers = {"Authorization": f"OAuth {access_token}"}
    params = {"limit": 200, "show_tracks": False}

    playlists = []

    try:
        while url:
            # Fetch metadata only - tracks loaded separately as needed
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Handle both list and dict responses
            if isinstance(data, list):
                collection = data
            elif isinstance(data, dict) and "collection" in data:
                collection = data["collection"]
            else:
                collection = []

            log(f"API response: type={type(data)}, has_collection={'collection' in data if isinstance(data, dict) else False}, collection_size={len(collection)}", level="debug")

            # Process playlists
            for playlist in collection:
                playlist_dict = {
                    "id": str(playlist["id"]),
                    "name": playlist.get("title", "Untitled"),
                    "track_count": playlist.get("track_count", 0),
                    "description": playlist.get("description"),
                    "permalink": playlist.get("permalink_url"),
                    "last_modified": playlist.get("last_modified"),
                    "created_at": playlist.get("created_at"),
                }

                # Include tracks if available (from show_tracks parameter)
                if "tracks" in playlist and playlist["tracks"]:
                    playlist_dict["tracks"] = [
                        (str(track["id"]), _normalize_soundcloud_track(track))
                        for track in playlist["tracks"]
                        if track  # Filter None values
                    ]

                playlists.append(playlist_dict)

            # Next page (only for dict responses with pagination)
            url = data.get("next_href") if isinstance(data, dict) else None
            params = {}  # Pagination URL contains all params

        log(f"get_playlists returning {len(playlists)} playlists", level="debug")
        return state, playlists

    except HTTPError as e:
        # Authentication failures (401/403) indicate expired/invalid token
        if e.response.status_code in (401, 403):
            log(
                "SoundCloud authentication expired. Please re-authenticate with: library auth soundcloud",
                level="error",
            )
            # Mark state as unauthenticated so caller can show proper message
            from dataclasses import replace
            state = replace(state, authenticated=False)
            return state, []
        else:
            # Other HTTP errors (rate limit, server errors, etc.)
            log(
                f"HTTP error fetching playlists (status {e.response.status_code}): {e}",
                level="error",
            )
            return state, []
    except Exception as e:
        # Network errors, JSON parsing errors, etc.
        log(f"Error fetching playlists: {e}", level="error")
        return state, []


def get_playlist_tracks(
    state: ProviderState, playlist_id: str
) -> Tuple[ProviderState, TrackList, Optional[str]]:
    """Get tracks in a SoundCloud playlist.

    Args:
        state: Current provider state
        playlist_id: SoundCloud playlist ID

    Returns:
        (state, [(track_id, metadata), ...], created_at_timestamp)
        created_at_timestamp is None (SoundCloud provides creation date in get_playlists())
    """
    if not state.authenticated:
        return state, [], None

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, [], None

    access_token = token_data["access_token"]

    # Fetch playlist tracks (using URN format)
    playlist_urn = _format_playlist_urn(playlist_id)
    url = f"{API_BASE_URL}/playlists/{playlist_urn}"
    headers = {"Authorization": f"OAuth {access_token}"}
    params = {"show_tracks": True}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        playlist_data = response.json()

        tracks = []
        for track in playlist_data.get("tracks", []):
            if track:
                track_id = str(track["id"])
                metadata = _normalize_soundcloud_track(track)
                tracks.append((track_id, metadata))

        # SoundCloud provides creation date in get_playlists(), not here
        return state, tracks, None

    except Exception as e:
        logger.error(f"Error fetching playlist tracks: {e}", exc_info=True)
        return state, [], None


def like_track(
    state: ProviderState, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Like a track on SoundCloud.

    Args:
        state: Current provider state (must be authenticated)
        track_id: SoundCloud track ID

    Returns:
        (new_state, success, error_message)
    """
    if not state.authenticated:
        return state, False, "Not authenticated with SoundCloud"

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, False, "Token expired and refresh failed"

    access_token = token_data["access_token"]

    # Track URN format: soundcloud:tracks:{id}
    track_urn = f"soundcloud:tracks:{track_id}"

    # Like endpoint
    url = f"{API_BASE_URL}/likes/tracks/{track_urn}"
    headers = {"Authorization": f"OAuth {access_token}"}

    try:
        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        return state, True, None

    except requests.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}"
        if e.response.status_code == 401:
            return state.with_authenticated(False), False, "Authentication failed (401)"
        elif e.response.status_code == 404:
            return state, False, f"Track not found (404): {track_id}"
        elif e.response.status_code == 429:
            return state, False, "Rate limit exceeded (429)"
        else:
            return state, False, f"HTTP error: {error_msg}"
    except requests.RequestException as e:
        return state, False, f"Network error: {str(e)}"
    except Exception as e:
        return state, False, f"Unexpected error: {str(e)}"


def unlike_track(
    state: ProviderState, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Unlike a track on SoundCloud.

    Args:
        state: Current provider state (must be authenticated)
        track_id: SoundCloud track ID

    Returns:
        (new_state, success, error_message)
    """
    if not state.authenticated:
        return state, False, "Not authenticated with SoundCloud"

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, False, "Token expired and refresh failed"

    access_token = token_data["access_token"]

    # Track URN format: soundcloud:tracks:{id}
    track_urn = f"soundcloud:tracks:{track_id}"

    # Unlike endpoint
    url = f"{API_BASE_URL}/likes/tracks/{track_urn}"
    headers = {"Authorization": f"OAuth {access_token}"}

    try:
        response = requests.delete(url, headers=headers, timeout=30)
        response.raise_for_status()
        return state, True, None

    except requests.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}"
        if e.response.status_code == 401:
            return state.with_authenticated(False), False, "Authentication failed (401)"
        elif e.response.status_code == 404:
            return state, False, f"Track not found or not liked (404): {track_id}"
        elif e.response.status_code == 429:
            return state, False, "Rate limit exceeded (429)"
        else:
            return state, False, f"HTTP error: {error_msg}"
    except requests.RequestException as e:
        return state, False, f"Network error: {str(e)}"
    except Exception as e:
        return state, False, f"Unexpected error: {str(e)}"


# ============================================================================
# Private helper functions (adapted from soundcloud-discovery)
# ============================================================================


def _get_client_credentials_token() -> str:
    """Get access token using Client Credentials flow (for public data).

    Returns:
        Access token for client credentials

    Raises:
        ValueError: If client credentials are not configured
    """
    tokens_file = auth._get_tokens_dir() / "app_token.json"

    # Try cached token
    if tokens_file.exists():
        with open(tokens_file) as f:
            token_data = json.load(f)

        if not auth.is_token_expired(token_data):
            return token_data["access_token"]

    # Load config to get client credentials
    from music_minion.core.config import load_config

    config = load_config()

    client_id = config.soundcloud.client_id
    client_secret = config.soundcloud.client_secret

    if not client_id or not client_secret:
        raise ValueError("SoundCloud client credentials not configured in config.toml")

    # Request new token
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )

        response.raise_for_status()
        token_data = response.json()

        # Add expiry timestamp
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        token_data["expires_at"] = expires_at.isoformat()

        # Save to cache
        with open(tokens_file, "w") as f:
            json.dump(token_data, f, indent=2)

        return token_data["access_token"]

    except Exception as e:
        raise ValueError(f"Failed to get client credentials token: {e}")


def _fetch_user_likes(
    access_token: str, existing_ids: Optional[set] = None, incremental: bool = True
) -> TrackList:
    """Fetch user's liked tracks from SoundCloud.

    Args:
        access_token: OAuth access token
        existing_ids: Set of SoundCloud IDs already in database (for incremental sync)
        incremental: If True, stop fetching when encountering an existing track

    Returns:
        List of (track_id, metadata) tuples
    """
    tracks, _ = _fetch_user_likes_with_markers(access_token, existing_ids, incremental)
    return tracks


def _fetch_user_likes_with_markers(
    access_token: str, existing_ids: Optional[set] = None, incremental: bool = True
) -> Tuple[TrackList, set]:
    """Fetch user's liked tracks from SoundCloud with all liked track IDs.

    Args:
        access_token: OAuth access token
        existing_ids: Set of SoundCloud IDs already in database (for incremental sync)
        incremental: If True, stop fetching when encountering an existing track

    Returns:
        (tracks, all_liked_ids)
        - tracks: List of (track_id, metadata) tuples for new tracks
        - all_liked_ids: Set of ALL liked track IDs (for marker sync)
    """
    if existing_ids is None:
        existing_ids = set()

    tracks = []
    all_liked_ids = set()  # Track ALL liked IDs for marker sync
    url = f"{API_BASE_URL}/me/likes/tracks"
    headers = {"Authorization": f"OAuth {access_token}"}

    # Pagination
    params = {
        "limit": 200,
        "linked_partitioning": True,  # Enable cursor-based pagination
        "access": "playable",
    }

    page = 0
    total_fetched = 0

    try:
        while url:
            page += 1
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Show pagination progress
            collection = data.get("collection", [])
            fetched_this_page = len(
                [item for item in collection if item and item.get("kind") == "track"]
            )

            # Process tracks
            page_tracks = 0
            found_existing = False

            if "collection" in data:
                for item in data["collection"]:
                    # Filter to only tracks (API may return other kinds)
                    if not item or item.get("kind") != "track":
                        continue

                    track_id = str(item["id"])
                    all_liked_ids.add(track_id)  # Always track ALL liked IDs

                    # Incremental sync: stop if we've already imported this track
                    if incremental and track_id in existing_ids:
                        found_existing = True
                        break

                    metadata = _normalize_soundcloud_track(item)
                    tracks.append((track_id, metadata))
                    page_tracks += 1

            total_fetched = len(all_liked_ids)

            # Show progress per page
            log(
                f"  → {total_fetched} (page {page}, +{fetched_this_page})", level="info"
            )

            # Incremental mode: Stop if we found an existing track
            if found_existing:
                log(
                    "  ✓ Stopping at first existing track (incremental mode)",
                    level="info",
                )
                break

            # Next page
            url = data.get("next_href")
            params = {}  # Pagination URL contains all params

    except HTTPError as e:
        # Authentication failures should be raised to caller
        if e.response.status_code in (401, 403):
            log(
                "SoundCloud authentication expired. Please re-authenticate with: library auth soundcloud",
                level="error",
            )
            raise  # Re-raise to let caller handle auth failure
        else:
            # Other HTTP errors - log but return what we have
            log(
                f"  ⚠ HTTP error fetching likes (status {e.response.status_code}): {e}",
                level="warning",
            )
    except Exception as e:
        # Network errors - show error but return what we have
        log(f"  ⚠ Error fetching likes: {e}", level="warning")

    log(f"  ✓ Fetched {total_fetched} liked tracks", level="info")
    return tracks, all_liked_ids


def _normalize_soundcloud_track(track: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize SoundCloud track data to standard metadata format."""
    metadata = {
        "title": track.get("title", "").strip(),
        "artist": (
            track.get("metadata_artist") or track.get("user", {}).get("username", "")
        ).strip(),
        "genre": track.get("genre", "").strip() if track.get("genre") else None,
        "duration": track.get("duration", 0) / 1000.0
        if track.get("duration")
        else None,  # ms to seconds
        "year": None,  # SoundCloud doesn't provide year in API
        "bpm": None,  # Initialize to None, set below if available
    }

    # BPM if available
    if track.get("bpm"):
        try:
            metadata["bpm"] = float(track["bpm"])
        except (ValueError, TypeError):
            pass

    # Keep None values for consistent field set across all tracks
    # This prevents "binding parameter" errors during batch insert
    return metadata


def add_track_to_playlist(
    state: ProviderState, playlist_id: str, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Add a track to a SoundCloud playlist.

    Strategy: SoundCloud uses PUT (full replacement), so we:
    1. GET current playlist tracks
    2. Append new track_id
    3. PUT updated list

    Args:
        state: Current provider state
        playlist_id: SoundCloud playlist ID
        track_id: SoundCloud track ID to add

    Returns:
        (new_state, success, error_message)
    """
    if not state.authenticated:
        return state, False, "Not authenticated with SoundCloud"

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, False, "Token expired and refresh failed"

    access_token = token_data["access_token"]

    try:
        # 1. Get current playlist (using URN format)
        playlist_urn = _format_playlist_urn(playlist_id)
        url = f"{API_BASE_URL}/playlists/{playlist_urn}"
        headers = {"Authorization": f"OAuth {access_token}"}

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        playlist_data = response.json()

        # 2. Extract track IDs and append new one
        current_tracks = playlist_data.get("tracks", [])
        track_ids = [str(t["id"]) for t in current_tracks if t]

        # Check if track already in playlist
        if track_id in track_ids:
            return state, False, "Track already in playlist"

        track_ids.append(track_id)

        # 3. Update playlist with new track list (using URN format for tracks)
        update_data = {
            "playlist": {
                "tracks": [{"urn": _format_track_urn(tid)} for tid in track_ids]
            }
        }

        logger.debug(f"Adding track to playlist - URL: {url}")
        logger.debug(f"Request payload: {json.dumps(update_data, indent=2)}")

        response = requests.put(url, headers=headers, json=update_data, timeout=30)
        response.raise_for_status()

        return state, True, None

    except requests.HTTPError as e:
        # Log full error details
        logger.error(f"HTTP error adding track to playlist: {e.response.status_code}")
        logger.error(f"Request URL: {url}")
        logger.error(f"Request payload: {json.dumps(update_data, indent=2)}")
        logger.error(f"Response body: {e.response.text}")

        if e.response.status_code == 401:
            return state.with_authenticated(False), False, "Authentication failed (401)"
        elif e.response.status_code == 404:
            return state, False, "Playlist or track not found (404)"
        elif e.response.status_code == 429:
            return state, False, "Rate limit exceeded (429)"
        else:
            # Include response body for debugging 500 errors
            try:
                error_detail = e.response.text[:500]  # First 500 chars of error
                return state, False, f"HTTP {e.response.status_code}: {error_detail}"
            except:
                return state, False, f"HTTP error: {e.response.status_code}"
    except requests.RequestException as e:
        logger.error(f"Network error adding track to playlist: {str(e)}", exc_info=True)
        return state, False, f"Network error: {str(e)}"
    except Exception as e:
        logger.error(
            f"Unexpected error adding track to playlist: {str(e)}", exc_info=True
        )
        return state, False, f"Unexpected error: {str(e)}"


def remove_track_from_playlist(
    state: ProviderState, playlist_id: str, track_id: str
) -> Tuple[ProviderState, bool, Optional[str]]:
    """Remove a track from a SoundCloud playlist.

    Strategy:
    1. GET current playlist tracks
    2. Remove track_id from list
    3. PUT updated list

    Args:
        state: Current provider state
        playlist_id: SoundCloud playlist ID
        track_id: SoundCloud track ID to remove

    Returns:
        (new_state, success, error_message)
    """
    if not state.authenticated:
        return state, False, "Not authenticated with SoundCloud"

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, False, "Token expired and refresh failed"

    access_token = token_data["access_token"]

    try:
        # 1. Get current playlist (using URN format)
        playlist_urn = _format_playlist_urn(playlist_id)
        url = f"{API_BASE_URL}/playlists/{playlist_urn}"
        headers = {"Authorization": f"OAuth {access_token}"}

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        playlist_data = response.json()

        # 2. Extract track IDs and remove target track
        current_tracks = playlist_data.get("tracks", [])
        track_ids = [str(t["id"]) for t in current_tracks if t]

        # Check if track in playlist
        if track_id not in track_ids:
            return state, False, "Track not in playlist"

        track_ids.remove(track_id)

        # 3. Update playlist with new track list (using URN format for tracks)
        update_data = {
            "playlist": {
                "tracks": [{"urn": _format_track_urn(tid)} for tid in track_ids]
            }
        }

        logger.debug(f"Removing track from playlist - URL: {url}")
        logger.debug(f"Request payload: {json.dumps(update_data, indent=2)}")

        response = requests.put(url, headers=headers, json=update_data, timeout=30)
        response.raise_for_status()

        return state, True, None

    except requests.HTTPError as e:
        # Log full error details
        logger.error(
            f"HTTP error removing track from playlist: {e.response.status_code}"
        )
        logger.error(f"Request URL: {url}")
        logger.error(f"Request payload: {json.dumps(update_data, indent=2)}")
        logger.error(f"Response body: {e.response.text}")

        if e.response.status_code == 401:
            return state.with_authenticated(False), False, "Authentication failed (401)"
        elif e.response.status_code == 404:
            return state, False, "Playlist or track not found (404)"
        elif e.response.status_code == 429:
            return state, False, "Rate limit exceeded (429)"
        else:
            # Include response body for debugging 500 errors
            try:
                error_detail = e.response.text[:500]  # First 500 chars of error
                return state, False, f"HTTP {e.response.status_code}: {error_detail}"
            except:
                return state, False, f"HTTP error: {e.response.status_code}"
    except requests.RequestException as e:
        logger.error(
            f"Network error removing track from playlist: {str(e)}", exc_info=True
        )
        return state, False, f"Network error: {str(e)}"
    except Exception as e:
        logger.error(
            f"Unexpected error removing track from playlist: {str(e)}", exc_info=True
        )
        return state, False, f"Unexpected error: {str(e)}"


def create_playlist(
    state: ProviderState, name: str, description: Optional[str] = None
) -> Tuple[ProviderState, Optional[str], Optional[str]]:
    """Create a new SoundCloud playlist.

    Args:
        state: Current provider state
        name: Playlist name
        description: Optional playlist description

    Returns:
        (new_state, playlist_id or None, error_message)
    """
    if not state.authenticated:
        return state, None, "Not authenticated with SoundCloud"

    # Ensure token is valid, refresh if needed
    state, token_data = _ensure_valid_token(state)
    if not token_data:
        return state, None, "Token expired and refresh failed"

    access_token = token_data["access_token"]

    try:
        url = f"{API_BASE_URL}/me/playlists"
        headers = {"Authorization": f"OAuth {access_token}"}

        data = {
            "playlist": {
                "title": name,
                "sharing": "public",
            }
        }

        if description:
            data["playlist"]["description"] = description

        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        playlist_data = response.json()

        playlist_id = str(playlist_data["id"])
        return state, playlist_id, None

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            return state.with_authenticated(False), None, "Authentication failed (401)"
        elif e.response.status_code == 429:
            return state, None, "Rate limit exceeded (429)"
        else:
            return state, None, f"HTTP error: {e.response.status_code}"
    except requests.RequestException as e:
        return state, None, f"Network error: {str(e)}"
    except Exception as e:
        return state, None, f"Unexpected error: {str(e)}"
