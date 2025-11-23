"""
Spotify → SoundCloud playlist conversion pipeline.

Orchestrates matching, database import, and playlist creation using
pure functional patterns with explicit state passing.
"""

import time
from typing import Any, Callable, NamedTuple

from loguru import logger

from ...core import database
from ...core.output import log
from ...domain.library import providers
from ...domain.library.provider import ProviderConfig
from .matching import (
    MIN_CONFIDENCE_THRESHOLD,
    MatchCandidate,
    batch_score_candidates,
    generate_search_queries,
)


class ConversionResult(NamedTuple):
    """Result of Spotify → SoundCloud playlist conversion."""

    success: bool
    total_tracks: int
    matched_tracks: int
    failed_tracks: int
    soundcloud_playlist_id: str | None
    soundcloud_playlist_url: str | None
    average_confidence: float
    unmatched_track_names: list[str]
    error_message: str | None


class TrackMatch(NamedTuple):
    """Match result for a single Spotify track."""

    spotify_id: str
    spotify_title: str
    spotify_artist: str
    matched: bool
    soundcloud_id: str | None
    soundcloud_title: str | None
    soundcloud_artist: str | None
    confidence: float
    search_query: str


def match_spotify_tracks_to_soundcloud(
    spotify_tracks: list[tuple[str, dict[str, Any]]],
    soundcloud_provider_state: Any,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[Any, list[TrackMatch]]:
    """Match Spotify tracks to SoundCloud using optimized batch scoring.

    Args:
        spotify_tracks: List of (track_id, metadata) tuples from Spotify
        soundcloud_provider_state: Initialized SoundCloud provider state
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        (updated_soundcloud_state, list of TrackMatch objects)
    """
    matches = []
    update_interval = max(1, len(spotify_tracks) // 100)  # Report every 1%

    for idx, (sp_id, sp_meta) in enumerate(spotify_tracks):
        sp_title = sp_meta["title"]
        sp_artist = sp_meta["artist"]

        # Generate search query variants
        search_queries = generate_search_queries(
            {
                "title": sp_title,
                "artist": sp_artist,
                "top_level_artist": sp_meta.get("top_level_artist", sp_artist),
            }
        )

        # Try multiple queries and collect unique results
        all_results: dict[str, dict[str, Any]] = {}
        best_query = search_queries[0]

        for query in search_queries[:3]:  # Limit to 3 queries
            soundcloud_provider_state, sc_results = providers.get_provider(
                "soundcloud"
            ).search(soundcloud_provider_state, query)

            if sc_results and len(sc_results) > len(all_results):
                best_query = query

            # Merge results (deduplicate by ID)
            for sc_id, meta in sc_results:
                if sc_id not in all_results:
                    all_results[sc_id] = meta

            time.sleep(0.1)  # Rate limiting

        # Score all candidates
        candidates_list = list(all_results.items())
        if candidates_list:
            scored_candidates = batch_score_candidates(
                {
                    "title": sp_title,
                    "artist": sp_artist,
                    "top_level_artist": sp_meta.get("top_level_artist", sp_artist),
                    "duration_ms": int(sp_meta.get("duration", 0) * 1000),
                },
                candidates_list,
            )

            if scored_candidates:
                best_match = scored_candidates[0]
                matches.append(
                    TrackMatch(
                        spotify_id=sp_id,
                        spotify_title=sp_title,
                        spotify_artist=sp_artist,
                        matched=True,
                        soundcloud_id=best_match.soundcloud_id,
                        soundcloud_title=best_match.soundcloud_title,
                        soundcloud_artist=best_match.soundcloud_artist,
                        confidence=best_match.confidence_score,
                        search_query=best_query,
                    )
                )
            else:
                # No match above threshold
                matches.append(
                    TrackMatch(
                        spotify_id=sp_id,
                        spotify_title=sp_title,
                        spotify_artist=sp_artist,
                        matched=False,
                        soundcloud_id=None,
                        soundcloud_title=None,
                        soundcloud_artist=None,
                        confidence=0.0,
                        search_query=best_query,
                    )
                )
        else:
            # No search results
            matches.append(
                TrackMatch(
                    spotify_id=sp_id,
                    spotify_title=sp_title,
                    spotify_artist=sp_artist,
                    matched=False,
                    soundcloud_id=None,
                    soundcloud_title=None,
                    soundcloud_artist=None,
                    confidence=0.0,
                    search_query=best_query,
                )
            )

        # Progress reporting
        if progress_callback and (idx + 1) % update_interval == 0:
            progress_callback(idx + 1, len(spotify_tracks))

    # Final progress update
    if progress_callback:
        progress_callback(len(spotify_tracks), len(spotify_tracks))

    return soundcloud_provider_state, matches


def import_soundcloud_tracks_to_db(matches: list[TrackMatch]) -> int:
    """Import matched SoundCloud tracks to database.

    Args:
        matches: List of TrackMatch objects with matched=True

    Returns:
        Number of tracks successfully imported
    """
    matched_tracks = [m for m in matches if m.matched and m.soundcloud_id]

    if not matched_tracks:
        return 0

    # Build track data for batch insert
    track_data = []
    for match in matched_tracks:
        track_data.append(
            (
                match.soundcloud_id,
                {
                    "title": match.soundcloud_title,
                    "artist": match.soundcloud_artist,
                    # Duration and other metadata would come from original search results
                    # For now, we'll let the database handle missing fields
                },
            )
        )

    try:
        with database.get_db_connection() as conn:
            database.batch_insert_provider_tracks(conn, "soundcloud", track_data)
        logger.info(f"Imported {len(track_data)} SoundCloud tracks to database")
        return len(track_data)
    except Exception as e:
        logger.exception(f"Failed to import SoundCloud tracks to database: {e}")
        return 0


def create_soundcloud_playlist(
    soundcloud_provider_state: Any,
    playlist_name: str,
    matched_track_ids: list[str],
) -> tuple[Any, str | None, str | None]:
    """Create SoundCloud playlist and add matched tracks.

    Args:
        soundcloud_provider_state: Initialized SoundCloud provider state
        playlist_name: Name for the new playlist
        matched_track_ids: List of SoundCloud track IDs to add

    Returns:
        (updated_state, playlist_id, error_message)
    """
    soundcloud = providers.get_provider("soundcloud")

    # Create playlist
    soundcloud_provider_state, playlist_id, error = soundcloud.create_playlist(
        soundcloud_provider_state, playlist_name, description="Converted from Spotify"
    )

    if not playlist_id:
        return soundcloud_provider_state, None, error or "Failed to create playlist"

    # Add tracks to playlist
    added_count = 0
    for track_id in matched_track_ids:
        soundcloud_provider_state, success, add_error = soundcloud.add_track_to_playlist(
            soundcloud_provider_state, playlist_id, track_id
        )

        if success:
            added_count += 1
        else:
            logger.warning(
                f"Failed to add track {track_id} to playlist: {add_error}"
            )

        time.sleep(0.1)  # Rate limiting

    logger.info(
        f"Added {added_count}/{len(matched_track_ids)} tracks to SoundCloud playlist {playlist_id}"
    )

    return soundcloud_provider_state, playlist_id, None


def convert_spotify_to_soundcloud(
    spotify_playlist_id: str,
    soundcloud_playlist_name: str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> ConversionResult:
    """Convert Spotify playlist to SoundCloud playlist.

    Main pipeline function that orchestrates all conversion steps.

    Args:
        spotify_playlist_id: Spotify playlist ID to convert
        soundcloud_playlist_name: Name for new SoundCloud playlist
        progress_callback: Optional callback(current, total) for progress

    Returns:
        ConversionResult with success status and statistics
    """
    try:
        # Initialize providers
        spotify = providers.get_provider("spotify")
        soundcloud = providers.get_provider("soundcloud")

        spotify_state = spotify.init_provider(
            ProviderConfig(name="spotify", enabled=True)
        )
        soundcloud_state = soundcloud.init_provider(
            ProviderConfig(name="soundcloud", enabled=True)
        )

        if not spotify_state.authenticated:
            return ConversionResult(
                success=False,
                total_tracks=0,
                matched_tracks=0,
                failed_tracks=0,
                soundcloud_playlist_id=None,
                soundcloud_playlist_url=None,
                average_confidence=0.0,
                unmatched_track_names=[],
                error_message="Spotify not authenticated",
            )

        if not soundcloud_state.authenticated:
            return ConversionResult(
                success=False,
                total_tracks=0,
                matched_tracks=0,
                failed_tracks=0,
                soundcloud_playlist_id=None,
                soundcloud_playlist_url=None,
                average_confidence=0.0,
                unmatched_track_names=[],
                error_message="SoundCloud not authenticated",
            )

        # Fetch Spotify playlist tracks
        log("🔍 Fetching Spotify playlist...", level="info")
        spotify_state, spotify_tracks, _ = spotify.get_playlist_tracks(
            spotify_state, spotify_playlist_id
        )

        if not spotify_tracks:
            return ConversionResult(
                success=False,
                total_tracks=0,
                matched_tracks=0,
                failed_tracks=0,
                soundcloud_playlist_id=None,
                soundcloud_playlist_url=None,
                average_confidence=0.0,
                unmatched_track_names=[],
                error_message="Spotify playlist is empty or not found",
            )

        log(f"✓ Found {len(spotify_tracks)} tracks", level="info")

        # Match tracks to SoundCloud
        log("🔎 Matching tracks to SoundCloud...", level="info")
        soundcloud_state, matches = match_spotify_tracks_to_soundcloud(
            spotify_tracks, soundcloud_state, progress_callback
        )

        matched = [m for m in matches if m.matched]
        unmatched = [m for m in matches if not m.matched]

        log(f"✓ Matched {len(matched)}/{len(matches)} tracks", level="info")

        if not matched:
            return ConversionResult(
                success=False,
                total_tracks=len(matches),
                matched_tracks=0,
                failed_tracks=len(matches),
                soundcloud_playlist_id=None,
                soundcloud_playlist_url=None,
                average_confidence=0.0,
                unmatched_track_names=[
                    f"{m.spotify_artist} - {m.spotify_title}" for m in unmatched
                ],
                error_message="No tracks matched",
            )

        # Import matched tracks to database
        # Note: This step may be skipped if tracks are already in DB
        # import_soundcloud_tracks_to_db(matches)

        # Create SoundCloud playlist and add tracks
        log("📝 Creating SoundCloud playlist...", level="info")
        matched_track_ids = [m.soundcloud_id for m in matched if m.soundcloud_id]

        soundcloud_state, playlist_id, error = create_soundcloud_playlist(
            soundcloud_state, soundcloud_playlist_name, matched_track_ids
        )

        if not playlist_id:
            return ConversionResult(
                success=False,
                total_tracks=len(matches),
                matched_tracks=len(matched),
                failed_tracks=len(unmatched),
                soundcloud_playlist_id=None,
                soundcloud_playlist_url=None,
                average_confidence=sum(m.confidence for m in matched) / len(matched),
                unmatched_track_names=[
                    f"{m.spotify_artist} - {m.spotify_title}" for m in unmatched
                ],
                error_message=error,
            )

        # Calculate statistics
        avg_confidence = sum(m.confidence for m in matched) / len(matched)
        playlist_url = f"https://soundcloud.com/you/sets/{playlist_id}"

        return ConversionResult(
            success=True,
            total_tracks=len(matches),
            matched_tracks=len(matched),
            failed_tracks=len(unmatched),
            soundcloud_playlist_id=playlist_id,
            soundcloud_playlist_url=playlist_url,
            average_confidence=avg_confidence,
            unmatched_track_names=[
                f"{m.spotify_artist} - {m.spotify_title}" for m in unmatched
            ],
            error_message=None,
        )

    except Exception as e:
        logger.exception(f"Conversion failed: {e}")
        return ConversionResult(
            success=False,
            total_tracks=0,
            matched_tracks=0,
            failed_tracks=0,
            soundcloud_playlist_id=None,
            soundcloud_playlist_url=None,
            average_confidence=0.0,
            unmatched_track_names=[],
            error_message=str(e),
        )
