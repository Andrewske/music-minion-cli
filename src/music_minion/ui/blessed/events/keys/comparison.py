"""Comparison mode (Elo rating) keyboard handlers."""

import dataclasses

from blessed.keyboard import Keystroke

from music_minion.core.output import log
from music_minion.domain.rating.database import (
    RatingCoverageFilters,
    RatingCoverageStats,
    get_or_create_rating,
    get_or_create_playlist_rating,
    get_ratings_coverage,
    record_comparison,
    record_playlist_comparison,
)
from music_minion.domain.rating.elo import (
    get_k_factor,
    select_strategic_pair,
    update_ratings,
)
from music_minion.ui.blessed.state import ComparisonState, InternalCommand, UIState

from .utils import parse_key


def handle_comparison_key(
    key: Keystroke, state: UIState
) -> tuple[UIState | None, InternalCommand | None]:
    """
    Handle keyboard input during comparison mode.

    Keyboard shortcuts:
    - Left Arrow: Highlight Track A (left side)
    - Right Arrow: Highlight Track B (right side)
    - Space: Play currently highlighted track
    - Enter: Choose highlighted track as winner, record comparison
    - A: Archive highlighted track (mark to never play again)
    - Esc / Q: Exit comparison mode, restore playback

    Args:
        key: blessed Keystroke
        state: Current UI state with comparison mode active

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Parse key event to get consistent event dictionary
    event = parse_key(key)

    # Arrow keys: Change highlighted track
    if event["type"] == "arrow_left":
        new_comparison = dataclasses.replace(comparison, highlighted="a")
        new_state = dataclasses.replace(state, comparison=new_comparison)
        return new_state, None

    elif event["type"] == "arrow_right":
        new_comparison = dataclasses.replace(comparison, highlighted="b")
        new_state = dataclasses.replace(state, comparison=new_comparison)
        return new_state, None

    # A: Archive highlighted track
    elif event["type"] == "char" and event["char"] and event["char"].lower() == "a":
        return handle_archive_track(state)

    # Space: Play highlighted track
    elif key == " " or event["type"] == "char" and event["char"] == " ":
        track = (
            comparison.track_a if comparison.highlighted == "a" else comparison.track_b
        )
        # Use InternalCommand to trigger playback
        return state, InternalCommand(
            action="comparison_play_track", data={"track": track}
        )

    # Enter: Choose highlighted track as winner
    elif event["type"] == "enter":
        return handle_comparison_choice(state, comparison.highlighted)

    # Esc or Q: Exit comparison mode
    elif event["type"] == "escape" or (
        event["type"] == "char" and event["char"] and event["char"].lower() == "q"
    ):
        return exit_comparison_mode(state)

    # Key not handled by comparison mode - allow fallthrough to normal handling
    return None, None


def handle_comparison_choice(
    state: UIState, winner_side: str
) -> tuple[UIState, InternalCommand | None]:
    """
    Record comparison, update ratings, load next pair or end session.

    Args:
        state: Current UI state
        winner_side: "a" or "b"

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Determine winner and loser
    if winner_side == "a":
        winner = comparison.track_a
        loser = comparison.track_b
    else:
        winner = comparison.track_b
        loser = comparison.track_a

    if comparison.playlist_ranking_mode and comparison.playlist_id:
        # Playlist ranking mode - use playlist-specific ratings
        winner_playlist_rating_obj = get_or_create_playlist_rating(
            winner["id"], comparison.playlist_id
        )
        loser_playlist_rating_obj = get_or_create_playlist_rating(
            loser["id"], comparison.playlist_id
        )

        # Get global ratings for reference
        winner_global_rating_obj = get_or_create_rating(winner["id"])
        loser_global_rating_obj = get_or_create_rating(loser["id"])

        # Calculate K-factors based on playlist comparison counts
        winner_k = get_k_factor(winner_playlist_rating_obj.comparison_count)
        loser_k = get_k_factor(loser_playlist_rating_obj.comparison_count)

        # Use average K-factor for update
        k = (winner_k + loser_k) / 2

        # Update playlist ratings using Elo
        new_winner_playlist_rating, new_loser_playlist_rating = update_ratings(
            winner_playlist_rating_obj.rating, loser_playlist_rating_obj.rating, k
        )

        # Record playlist comparison in database
        record_playlist_comparison(
            track_a_id=comparison.track_a["id"],
            track_b_id=comparison.track_b["id"],
            winner_id=winner["id"],
            playlist_id=comparison.playlist_id,
            track_a_playlist_rating_before=winner_playlist_rating_obj.rating
            if winner_side == "a"
            else loser_playlist_rating_obj.rating,
            track_b_playlist_rating_before=loser_playlist_rating_obj.rating
            if winner_side == "a"
            else winner_playlist_rating_obj.rating,
            track_a_playlist_rating_after=new_winner_playlist_rating
            if winner_side == "a"
            else new_loser_playlist_rating,
            track_b_playlist_rating_after=new_loser_playlist_rating
            if winner_side == "a"
            else new_winner_playlist_rating,
            track_a_global_rating_before=winner_global_rating_obj.rating,
            track_b_global_rating_before=loser_global_rating_obj.rating,
            track_a_global_rating_after=winner_global_rating_obj.rating,  # No change for global
            track_b_global_rating_after=loser_global_rating_obj.rating,  # No change for global
            session_id=comparison.session_id,
        )

        # Use playlist ratings for display/cache updates
        new_winner_rating = new_winner_playlist_rating
        new_loser_rating = new_loser_playlist_rating
        winner_rating_obj = winner_playlist_rating_obj
        loser_rating_obj = loser_playlist_rating_obj

    else:
        # Standard global rating mode
        winner_rating_obj = get_or_create_rating(winner["id"])
        loser_rating_obj = get_or_create_rating(loser["id"])

        # Calculate K-factors
        winner_k = get_k_factor(winner_rating_obj.comparison_count)
        loser_k = get_k_factor(loser_rating_obj.comparison_count)

        # Use average K-factor for update
        k = (winner_k + loser_k) / 2

        # Update ratings using Elo
        new_winner_rating, new_loser_rating = update_ratings(
            winner_rating_obj.rating, loser_rating_obj.rating, k
        )

        # Record comparison in database
        record_comparison(
            track_a_id=comparison.track_a["id"],
            track_b_id=comparison.track_b["id"],
            winner_id=winner["id"],
            track_a_rating_before=winner_rating_obj.rating
            if winner_side == "a"
            else loser_rating_obj.rating,
            track_b_rating_before=loser_rating_obj.rating
            if winner_side == "a"
            else winner_rating_obj.rating,
            track_a_rating_after=new_winner_rating
            if winner_side == "a"
            else new_loser_rating,
            track_b_rating_after=new_loser_rating
            if winner_side == "a"
            else new_winner_rating,
            session_id=comparison.session_id,
        )

    # Increment comparison count
    new_comparisons_done = comparison.comparisons_done + 1

    # Load next pair
    # Get filtered tracks from comparison state (stored by command handler)
    filtered_tracks = comparison.filtered_tracks
    ratings_cache = comparison.ratings_cache or {}

    # Update ratings cache
    ratings_cache[winner["id"]] = {
        "rating": new_winner_rating,
        "comparison_count": winner_rating_obj.comparison_count + 1,
    }
    ratings_cache[loser["id"]] = {
        "rating": new_loser_rating,
        "comparison_count": loser_rating_obj.comparison_count + 1,
    }

    coverage_library_stats = _update_cached_coverage_stats(
        comparison.coverage_library_stats,
        winner_rating_obj.comparison_count,
        loser_rating_obj.comparison_count,
    )
    coverage_filter_stats = _update_cached_coverage_stats(
        comparison.coverage_filter_stats,
        winner_rating_obj.comparison_count,
        loser_rating_obj.comparison_count,
    )

    # Select next pair
    if not filtered_tracks or len(filtered_tracks) < 2:
        # Unexpected: no tracks to compare
        log("No more tracks to compare", level="warning")
        return end_comparison_session(state)

    track_a, track_b = select_strategic_pair(filtered_tracks, ratings_cache)

    # Update comparison state
    new_comparison = dataclasses.replace(
        comparison,
        track_a=track_a,
        track_b=track_b,
        highlighted="a",  # Reset to track A
        comparisons_done=new_comparisons_done,
        ratings_cache=ratings_cache,
        coverage_library_stats=coverage_library_stats,
        coverage_filter_stats=coverage_filter_stats,
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)

    return new_state, None


def end_comparison_session(state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    End comparison session, show summary, restore playback.

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Get coverage stats
    library_stats = _ensure_coverage_stats(
        comparison.coverage_library_stats, comparison.coverage_library_filters
    )
    filter_stats = (
        _ensure_coverage_stats(
            comparison.coverage_filter_stats, comparison.coverage_filter_filters
        )
        if _comparison_has_active_filters(comparison)
        else None
    )

    # Show session complete message
    log(
        f"Session complete! {comparison.comparisons_done} comparisons made.",
        level="info",
    )
    _log_coverage_summary(_library_scope_label(comparison), library_stats)
    if filter_stats:
        _log_coverage_summary(_filter_scope_label(comparison), filter_stats)

    # Clear comparison state
    new_comparison = dataclasses.replace(
        comparison,
        active=False,
        track_a=None,
        track_b=None,
        saved_player_state=None,
        filtered_tracks=[],
        ratings_cache=None,
        coverage_library_stats=None,
        coverage_filter_stats=None,
        coverage_library_filters=None,
        coverage_filter_filters=None,
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)
    return new_state, None


def _update_cached_coverage_stats(
    stats: RatingCoverageStats | None,
    winner_prev_count: int,
    loser_prev_count: int,
) -> RatingCoverageStats | None:
    """Return updated coverage stats with cached increments applied."""

    if not stats:
        return None

    compared_tracks = stats["tracks_with_comparisons"]
    if winner_prev_count == 0:
        compared_tracks += 1
    if loser_prev_count == 0:
        compared_tracks += 1

    total_comparisons = stats["total_comparisons"] + 2
    total_tracks = stats["total_tracks"]
    coverage_percent = compared_tracks / total_tracks * 100 if total_tracks else 0.0
    average_per_track = total_comparisons / total_tracks if total_tracks else 0.0
    average_per_compared = (
        total_comparisons / compared_tracks if compared_tracks else 0.0
    )

    return RatingCoverageStats(
        tracks_with_comparisons=compared_tracks,
        total_tracks=total_tracks,
        total_comparisons=total_comparisons,
        coverage_percent=coverage_percent,
        average_comparisons_per_track=average_per_track,
        average_comparisons_per_compared_track=average_per_compared,
    )


def _ensure_coverage_stats(
    stats: RatingCoverageStats | None,
    filters: RatingCoverageFilters | None,
) -> RatingCoverageStats:
    """Return cached stats if available, otherwise refresh from database."""

    if stats:
        return stats
    return get_ratings_coverage(filters)


def _comparison_has_active_filters(comparison: ComparisonState) -> bool:
    return any(
        [
            comparison.playlist_id is not None,
            comparison.genre_filter,
            comparison.year_filter,
        ]
    )


def _library_scope_label(comparison: ComparisonState) -> str:
    source = comparison.source_filter or "all sources"
    if source == "all":
        source = "all sources"
    return f"Library ({source})"


def _filter_scope_label(comparison: ComparisonState) -> str:
    parts: list[str] = []
    if comparison.playlist_id is not None:
        parts.append(f"playlist={comparison.playlist_id}")
    if comparison.genre_filter:
        parts.append(f"genre={comparison.genre_filter}")
    if comparison.year_filter:
        parts.append(f"year={comparison.year_filter}")
    if not parts:
        return "Filters"
    return f"Filters ({', '.join(parts)})"


def _log_coverage_summary(label: str, stats: RatingCoverageStats) -> None:
    log(
        f"{label}: {stats['tracks_with_comparisons']}/{stats['total_tracks']} "
        f"({stats['coverage_percent']:.1f}% coverage)",
        level="info",
    )
    log(
        f"{label} averages: {stats['average_comparisons_per_track']:.2f} per track, "
        f"{stats['average_comparisons_per_compared_track']:.2f} per compared track",
        level="info",
    )


def exit_comparison_mode(state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    Exit comparison mode early (user pressed Esc).

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Show exit message
    log(
        f"Session ended. {comparison.comparisons_done} comparisons completed.",
        level="info",
    )

    # Clear comparison state
    new_comparison = dataclasses.replace(
        comparison,
        active=False,
        track_a=None,
        track_b=None,
        saved_player_state=None,
        filtered_tracks=[],
        ratings_cache=None,
        coverage_library_stats=None,
        coverage_filter_stats=None,
        coverage_library_filters=None,
        coverage_filter_filters=None,
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)

    return new_state, None


def handle_archive_track(state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    Archive the highlighted track (mark to never play again) and load next pair.

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    from music_minion.core import database

    comparison = state.comparison
    track = comparison.track_a if comparison.highlighted == "a" else comparison.track_b

    if not track:
        log("No track to archive", level="warning")
        return state, None

    track_id = track.get("id")
    if not track_id:
        log("Track has no ID", level="error")
        return state, None

    # Archive the track
    database.add_rating(track_id, "archive", "Archived during comparison")
    title = track.get("title", "Unknown")
    artist = track.get("artist", "Unknown")
    log(f"📦 Archived: {artist} - {title}", level="info")

    # Remove archived track from filtered_tracks to prevent it appearing again
    filtered_tracks = [t for t in comparison.filtered_tracks if t.get("id") != track_id]

    # Check if we still have enough tracks
    if len(filtered_tracks) < 2:
        log("Not enough tracks remaining after archive", level="warning")
        return end_comparison_session(state)

    # Select a new pair (replacing the archived track)
    ratings_cache = comparison.ratings_cache or {}
    track_a, track_b = select_strategic_pair(filtered_tracks, ratings_cache)

    # Update comparison state
    new_comparison = dataclasses.replace(
        comparison,
        track_a=track_a,
        track_b=track_b,
        highlighted="a",
        filtered_tracks=filtered_tracks,
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)
    return new_state, None
