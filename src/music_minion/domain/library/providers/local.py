"""
Local filesystem provider for Music Minion.

Scans local music directories and provides access to files.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..metadata import extract_track_metadata
from ..provider import ProviderConfig, ProviderState, TrackList


def init_provider(config: ProviderConfig) -> ProviderState:
    """Initialize local file provider.

    Args:
        config: Provider configuration

    Returns:
        Initial provider state (already "authenticated" for local files)
    """
    return ProviderState(
        config=config,
        authenticated=True,  # No auth needed for local files
        last_sync=None,
        cache={},
    )


def authenticate(state: ProviderState) -> Tuple[ProviderState, bool]:
    """Authenticate with local filesystem.

    No-op for local provider - always authenticated.

    Args:
        state: Current provider state

    Returns:
        (state, True) - always successful
    """
    return state.with_authenticated(True), True


def sync_library(state: ProviderState) -> Tuple[ProviderState, TrackList]:
    """Scan local music directories and return tracks.

    Args:
        state: Current provider state

    Returns:
        (new_state, [(local_path, metadata), ...])
    """
    # Get library paths from config
    # Note: This will be injected via the full Config object in practice
    # For now, return empty list - full integration happens in Phase 7

    # Placeholder - will be implemented when integrating with main app
    tracks: TrackList = []

    new_state = state.with_sync_time()
    return new_state, tracks


def search(state: ProviderState, query: str) -> Tuple[ProviderState, TrackList]:
    """Search local files by filename/metadata.

    Args:
        state: Current provider state
        query: Search query

    Returns:
        (state, [(local_path, metadata), ...])

    Note:
        For local provider, search is better handled at database level.
        This function is a placeholder for protocol compliance.
    """
    # Search is better done via database queries for local files
    return state, []


def get_stream_url(state: ProviderState, provider_id: str) -> Optional[str]:
    """Get playback path for local file.

    Args:
        state: Current provider state
        provider_id: File path

    Returns:
        Absolute file path if exists, None otherwise
    """
    local_path = Path(provider_id).expanduser()
    if local_path.exists() and local_path.is_file():
        return str(local_path.absolute())
    return None


def get_playlists(state: ProviderState) -> Tuple[ProviderState, List[Dict[str, Any]]]:
    """Get playlists from local filesystem.

    Args:
        state: Current provider state

    Returns:
        (state, []) - local provider doesn't have playlists

    Note:
        Playlists are managed in the database, not at provider level.
    """
    return state, []


def get_playlist_tracks(
    state: ProviderState, playlist_id: str
) -> Tuple[ProviderState, TrackList, Optional[str]]:
    """Get tracks in a local playlist.

    Args:
        state: Current provider state
        playlist_id: Playlist ID

    Returns:
        (state, [], None) - local provider doesn't have playlists

    Note:
        Playlists are managed in the database, not at provider level.
    """
    return state, [], None


def scan_local_library(
    library_paths: List[str], supported_formats: List[str], recursive: bool = True
) -> TrackList:
    """Scan local music directories and return track data.

    Helper function that can be called directly with config parameters.

    Args:
        library_paths: List of directory paths to scan
        supported_formats: List of file extensions (e.g., ['.mp3', '.m4a'])
        recursive: Whether to scan subdirectories

    Returns:
        [(local_path, metadata), ...]
    """
    tracks: TrackList = []

    for library_path in library_paths:
        path = Path(library_path).expanduser()

        if not path.exists() or not path.is_dir():
            continue

        # Find all music files
        files = path.rglob("*") if recursive else path.iterdir()

        for local_path in files:
            if not local_path.is_file():
                continue

            # Check if supported format
            if local_path.suffix.lower() not in supported_formats:
                continue

            # Extract metadata
            try:
                track = extract_track_metadata(str(local_path))
                metadata = {
                    "title": track.title,
                    "artist": track.artist,
                    "remix_artist": track.remix_artist,
                    "album": track.album,
                    "genre": track.genre,
                    "year": track.year,
                    "duration": track.duration,
                    "bpm": track.bpm,
                    "key": track.key,
                }
                # Remove None values
                metadata = {k: v for k, v in metadata.items() if v is not None}

                tracks.append((str(local_path.absolute()), metadata))
            except Exception:
                # Skip files that can't be read
                continue

    return tracks
