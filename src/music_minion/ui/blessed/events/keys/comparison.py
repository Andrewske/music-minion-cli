"""Comparison mode (Elo rating) keyboard handlers."""

import dataclasses

from blessed.keyboard import Keystroke
from loguru import logger

from music_minion.core.output import log
from music_minion.domain.rating.database import (
    RankingComplete,
    get_next_playlist_pair,
    get_or_create_playlist_rating,
    record_playlist_comparison,
)
from music_minion.domain.rating.elo import (
    get_k_factor,
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
    Record comparison winner (always playlist-based now).

    Args:
        state: Current UI state
        winner_side: "a" or "b"

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Always require playlist_id
    if not comparison.playlist_id:
        logger.error("No playlist selected for comparison")
        return state, None

    # Determine winner and loser
    if winner_side == "a":
        winner = comparison.track_a
        loser = comparison.track_b
    else:
        winner = comparison.track_b
        loser = comparison.track_a

    # Get playlist-specific ratings
    winner_rating_obj = get_or_create_playlist_rating(
        winner["id"], comparison.playlist_id
    )
    loser_rating_obj = get_or_create_playlist_rating(loser["id"], comparison.playlist_id)

    # Calculate K-factors based on playlist comparison counts
    winner_k = get_k_factor(winner_rating_obj.comparison_count)
    loser_k = get_k_factor(loser_rating_obj.comparison_count)

    # Use average K-factor for update
    k = (winner_k + loser_k) / 2

    # Update playlist ratings using Elo
    new_winner_rating, new_loser_rating = update_ratings(
        winner_rating_obj.rating, loser_rating_obj.rating, k
    )

    # Record comparison without session_id, single transaction
    try:
        record_playlist_comparison(
            playlist_id=comparison.playlist_id,
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
            session_id="",  # Empty string for sessionless
        )
    except Exception as e:
        logger.exception("Failed to record comparison")
        return state, None

    # Increment comparison count
    new_comparisons_done = comparison.comparisons_done + 1

    # Get next pair (stateless)
    try:
        track_a, track_b = get_next_playlist_pair(comparison.playlist_id)

        # Update comparison state with next pair
        new_comparison = dataclasses.replace(
            comparison,
            track_a=track_a,
            track_b=track_b,
            highlighted="a",  # Reset to track A
            comparisons_done=new_comparisons_done,
        )

        new_state = dataclasses.replace(state, comparison=new_comparison)
        return new_state, None

    except RankingComplete:
        # Show completion message
        log("🎉 Ranking complete! All tracks compared.", level="info")
        return end_comparison_session(state)


def end_comparison_session(state: UIState) -> tuple[UIState, InternalCommand | None]:
    """
    End comparison session, show summary.

    Args:
        state: Current UI state

    Returns:
        Tuple of (updated state, command to execute or None)
    """
    comparison = state.comparison

    # Show session complete message
    log(
        f"Session complete! {comparison.comparisons_done} comparisons made.",
        level="info",
    )

    # Clear comparison state
    new_comparison = dataclasses.replace(
        comparison,
        active=False,
        track_a=None,
        track_b=None,
        filtered_tracks=[],
        ratings_cache=None,
        coverage_library_stats=None,
        coverage_filter_stats=None,
    )

    new_state = dataclasses.replace(state, comparison=new_comparison)
    return new_state, None


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
        filtered_tracks=[],
        ratings_cache=None,
        coverage_library_stats=None,
        coverage_filter_stats=None,
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

    # Get next pair (stateless) - archived track will be excluded by playlist membership
    try:
        track_a, track_b = get_next_playlist_pair(comparison.playlist_id)

        # Update comparison state
        new_comparison = dataclasses.replace(
            comparison,
            track_a=track_a,
            track_b=track_b,
            highlighted="a",
        )

        new_state = dataclasses.replace(state, comparison=new_comparison)
        return new_state, None

    except RankingComplete:
        log("Ranking complete after archive", level="info")
        return end_comparison_session(state)
