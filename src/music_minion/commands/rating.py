"""
Rating command handlers for Music Minion CLI.

Handles: archive, like, love, note, unlike, rankings, rate
"""

import uuid
from datetime import datetime
from typing import Optional

from loguru import logger

from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.output import log
from music_minion.domain import library
from music_minion.domain.rating.database import (
    RatingCoverageFilters,
    RatingCoverageStats,
    get_ratings_coverage,
)


def handle_archive_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Handle archive command - mark current song to never play again.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add archive rating
    database.add_rating(track_id, "archive", "User archived song")
    log(f"📦 Archived: {library.get_display_name(current_track)}", level="info")
    log("   This song will not be played in future shuffle sessions", level="info")

    # Skip to next track automatically
    from .playback import handle_skip_command

    return handle_skip_command(ctx)


def handle_like_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Handle like command - rate current song as liked.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add like rating
    database.add_rating(track_id, "like", "User liked song", source="user")
    log(f"👍 Liked: {library.get_display_name(current_track)}", level="info")

    # Show temporal context
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
    log(f"   Liked on {time_context}", level="info")

    # Sync to SoundCloud if track has soundcloud_id
    soundcloud_id = db_track.get("soundcloud_id")
    if soundcloud_id:
        # Check if already liked on SoundCloud
        if not database.has_soundcloud_like(track_id):
            # Sync like to SoundCloud
            from music_minion.domain.library import providers

            try:
                # Get SoundCloud provider
                provider = providers.get_provider("soundcloud")
                from music_minion.domain.library.provider import ProviderConfig

                config = ProviderConfig(name="soundcloud", enabled=True)
                state = provider.init_provider(config)

                if state.authenticated:
                    # Call API to like track
                    new_state, success, error_msg = provider.like_track(
                        state, soundcloud_id
                    )

                    if success:
                        # Add soundcloud marker to database
                        database.add_rating(
                            track_id,
                            "like",
                            "Synced to SoundCloud",
                            source="soundcloud",
                        )
                        log("   ✓ Synced like to SoundCloud", level="info")
                    else:
                        log(
                            f"   ⚠ Failed to sync to SoundCloud: {error_msg}",
                            level="warning",
                        )
                        log("     Check logs for details", level="warning")
                else:
                    # Not authenticated - skip silently
                    pass
            except Exception as e:
                log(f"   ⚠ Error syncing to SoundCloud: {e}", level="warning")
                log("     Check logs for details", level="warning")

    return ctx, True


def handle_love_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Handle love command - rate current song as loved.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add love rating
    database.add_rating(track_id, "love", "User loved song")
    log(f"❤️  Loved: {library.get_display_name(current_track)}", level="info")

    # Show temporal context and DJ info
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
    log(f"   Loved on {time_context}", level="info")

    dj_info = library.get_dj_info(current_track)
    if dj_info != "No DJ metadata":
        log(f"   {dj_info}", level="info")

    return ctx, True


def handle_note_command(ctx: AppContext, args: list[str]) -> tuple[AppContext, bool]:
    """Handle note command - add a note to the current song.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not args:
        log("Error: Please provide a note. Usage: note <text>", level="error")
        return ctx, True

    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    # Add note
    note_text = " ".join(args)
    note_id = database.add_note(track_id, note_text)

    log(f"📝 Note added to: {library.get_display_name(current_track)}", level="info")
    log(f'   "{note_text}"', level="info")

    # Show temporal context
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"
    log(f"   Added on {time_context}", level="info")

    if note_id:
        log(f"   Note ID: {note_id} (for AI processing)", level="info")

    return ctx, True


def handle_unlike_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Handle unlike command - remove SoundCloud like for current track.

    Only removes the SoundCloud like marker and syncs to SoundCloud.
    Does not remove local user likes (those are temporal data).

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        log("No track is currently playing", level="warning")
        return ctx, True

    # Get track ID from player state (works for both local and streaming tracks)
    track_id = ctx.player_state.current_track_id

    # Fallback to path lookup for backward compatibility
    if not track_id:
        db_track = database.get_track_by_path(ctx.player_state.current_track)
        if not db_track:
            log("❌ Could not find current track in database", level="error")
            return ctx, True
        track_id = db_track["id"]

    # Get full track info from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        log("❌ Could not find current track in database", level="error")
        return ctx, True

    # Find Track object in memory for display (multi-source lookup)
    current_track = None
    for track in ctx.music_tracks:
        if (
            (track.local_path and track.local_path == db_track.get("local_path"))
            or (
                track.soundcloud_id
                and track.soundcloud_id == db_track.get("soundcloud_id")
            )
            or (track.spotify_id and track.spotify_id == db_track.get("spotify_id"))
            or (track.youtube_id and track.youtube_id == db_track.get("youtube_id"))
        ):
            current_track = track
            break

    if not current_track:
        log("Could not find current track information", level="error")
        return ctx, True

    soundcloud_id = db_track.get("soundcloud_id")

    # Check if track has SoundCloud like marker
    if not database.has_soundcloud_like(track_id):
        log(f"⚠ {library.get_display_name(current_track)}", level="warning")
        log("   Track is not liked on SoundCloud", level="warning")
        return ctx, True

    # Track has SoundCloud like, proceed to unlike
    if not soundcloud_id:
        log(f"⚠ {library.get_display_name(current_track)}", level="warning")
        log("   Track has like marker but no SoundCloud ID", level="warning")
        return ctx, True

    # Remove SoundCloud like via API
    from music_minion.domain.library import providers

    try:
        # Get SoundCloud provider
        provider = providers.get_provider("soundcloud")
        from music_minion.domain.library.provider import ProviderConfig

        config = ProviderConfig(name="soundcloud", enabled=True)
        state = provider.init_provider(config)

        if not state.authenticated:
            log("⚠ Not authenticated with SoundCloud", level="warning")
            log("   Run: library auth soundcloud", level="warning")
            return ctx, True

        # Call API to unlike track
        new_state, success, error_msg = provider.unlike_track(state, soundcloud_id)

        if success:
            # Remove soundcloud marker from database
            with database.get_db_connection() as conn:
                conn.execute(
                    "DELETE FROM ratings WHERE track_id = ? AND source = 'soundcloud'",
                    (track_id,),
                )
                conn.commit()

            log(
                f"💔 Unliked on SoundCloud: {library.get_display_name(current_track)}",
                level="info",
            )
            log("   ✓ Removed like from SoundCloud", level="info")
        else:
            log(f"⚠ Failed to unlike on SoundCloud: {error_msg}", level="warning")
            log("   Check logs for details", level="warning")

    except Exception as e:
        log(f"⚠ Error unliking on SoundCloud: {e}", level="warning")
        log("   Check logs for details", level="warning")

    return ctx, True


def parse_rankings_args(args: list[str]) -> dict:
    """Parse /rankings command arguments.

    Args:
        args: Command line arguments

    Returns:
        Dictionary with parsed arguments: limit, genre, year
    """
    result = {"limit": 50, "genre": None, "year": None}

    for arg in args:
        if arg.startswith("--limit="):
            try:
                result["limit"] = int(arg.split("=", 1)[1])
            except ValueError:
                logger.warning(f"Invalid limit value: {arg}")
        elif arg.startswith("--genre="):
            result["genre"] = arg.split("=", 1)[1]
        elif arg.startswith("--year="):
            try:
                result["year"] = int(arg.split("=", 1)[1])
            except ValueError:
                logger.warning(f"Invalid year value: {arg}")

    return result


def handle_rankings_command(
    ctx: AppContext, args: list[str]
) -> tuple[AppContext, bool]:
    """Display top-rated tracks in command palette.

    Args:
        ctx: Application context
        args: Command arguments (--genre=X, --year=Y, --limit=N)

    Returns:
        (updated_context, should_continue)

    Examples:
        rankings                    # Top 50 tracks globally
        rankings --genre=dubstep    # Top dubstep tracks
        rankings --year=2025        # Top 2025 tracks
        rankings --limit=100        # Top 100 tracks
    """
    from music_minion.domain.rating.database import get_leaderboard

    # Parse arguments
    parsed = parse_rankings_args(args)

    # Load leaderboard from database
    try:
        tracks = get_leaderboard(
            limit=parsed["limit"],
            min_comparisons=1,  # Show any track with at least 1 comparison
            genre_filter=parsed["genre"],
            year_filter=parsed["year"],
        )
    except Exception as e:
        logger.exception("Error loading leaderboard")
        log(f"Error loading rankings: {e}", level="error")
        return ctx, True

    # Handle empty results
    if not tracks:
        log("No rated tracks found matching filters.", level="warning")
        return ctx, True

    # Build title with filter info
    title = "Top Rated Tracks"
    if parsed["genre"] or parsed["year"]:
        filters = []
        if parsed["genre"]:
            filters.append(parsed["genre"].capitalize())
        if parsed["year"]:
            filters.append(str(parsed["year"]))
        title = f"Top Rated: {' • '.join(filters)}"

    # Show in rankings palette using UI action
    ctx = ctx.with_ui_action(
        {
            "type": "show_rankings_palette",
            "tracks": tracks,
            "title": title,
        }
    )

    return ctx, True


def _load_comparison_data_background(
    ctx: AppContext,
    session_id: str,
    count: int,
    source_filter: str,
    genre_filter: Optional[str],
    year_filter: Optional[int],
    playlist_id: Optional[int],
    saved_player_state: any,
) -> None:
    """Background worker to load tracks and select comparison pair.

    Args:
        ctx: Application context
        session_id: Comparison session ID
        count: Target number of comparisons
        source_filter: Source filter ('local', 'spotify', etc.)
        genre_filter: Optional genre filter
        year_filter: Optional year filter
        playlist_id: Optional playlist ID filter
        saved_player_state: Saved player state before session
    """
    import threading
    from datetime import datetime

    from music_minion.domain.rating.database import get_filtered_tracks
    from music_minion.domain.rating.elo import select_strategic_pair
    from music_minion.ui.blessed.state import ComparisonState

    # Mark thread as silent (suppress stdout in blessed UI)
    threading.current_thread().silent_logging = True

    try:
        # Load and filter tracks
        tracks = get_filtered_tracks(
            genre=genre_filter,
            year=year_filter,
            playlist_id=playlist_id,
            source_filter=source_filter,
        )

        # Validate track count
        if len(tracks) < 2:
            if ctx.update_ui_state:
                ctx.update_ui_state(
                    {
                        "comparison": ComparisonState(active=False),
                        "history_messages": [
                            (
                                f"❌ Need at least 2 tracks for comparison. Found {len(tracks)}.",
                                "red",
                            )
                        ],
                    }
                )
            return

        # Build ratings cache (fast - data already in tracks from JOIN)
        ratings_cache = {
            track["id"]: {
                "rating": track["rating"],
                "comparison_count": track["comparison_count"],
            }
            for track in tracks
        }

        # Select first pair using strategic pairing
        track_a, track_b = select_strategic_pair(tracks, ratings_cache)

        (
            library_stats,
            filter_stats,
            library_filters,
            filter_filters,
        ) = _load_coverage_stats_for_session(
            source_filter, genre_filter, year_filter, playlist_id
        )

        # Create loaded comparison state
        comparison = ComparisonState(
            active=True,
            loading=False,  # Done loading
            track_a=track_a,
            track_b=track_b,
            highlighted="a",
            session_id=session_id,
            comparisons_done=0,
            target_comparisons=count,
            playlist_id=playlist_id,
            genre_filter=genre_filter,
            year_filter=year_filter,
            source_filter=source_filter,
            session_start=datetime.now(),
            saved_player_state=saved_player_state,
            filtered_tracks=tracks,
            ratings_cache=ratings_cache,
            coverage_library_stats=library_stats,
            coverage_filter_stats=filter_stats,
            coverage_library_filters=library_filters,
            coverage_filter_filters=filter_filters,
        )

        # Update UI state from background thread
        if ctx.update_ui_state:
            # Build filter description for log message
            filter_parts = []
            if source_filter and source_filter != "all":
                filter_parts.append(f"{source_filter}")
            if genre_filter:
                filter_parts.append(f"genre={genre_filter}")
            if year_filter:
                filter_parts.append(f"year={year_filter}")
            if playlist_id:
                filter_parts.append(f"playlist={playlist_id}")

            filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""

            ctx.update_ui_state(
                {
                    "comparison": comparison,
                    "history_messages": [
                        (
                            f"🎵 Starting rating session: {count} comparisons, {len(tracks)} tracks{filter_desc}",
                            "green",
                        )
                    ],
                }
            )

        logger.info(
            f"Loaded comparison data: {len(tracks)} tracks, session_id={session_id}, "
            f"track_a={track_a.get('title') if track_a else None}, "
            f"track_b={track_b.get('title') if track_b else None}, "
            f"comparison.active={comparison.active}, comparison.loading={comparison.loading}"
        )

    except Exception as e:
        logger.exception("Failed to load comparison data in background")
        if ctx.update_ui_state:
            ctx.update_ui_state(
                {
                    "comparison": ComparisonState(active=False),
                    "history_messages": [(f"❌ Failed to load tracks: {e}", "red")],
                }
            )


def _build_coverage_filter_sets(
    source_filter: Optional[str],
    genre_filter: Optional[str],
    year_filter: Optional[int],
    playlist_id: Optional[int],
) -> tuple[Optional[RatingCoverageFilters], Optional[RatingCoverageFilters]]:
    """Return (library_filters, filter_filters) for coverage queries.

    library_filters: Only source_filter applied (library-wide scope)
    filter_filters: All filters applied (active filter scope)

    Returns None if no filters are active for that scope.
    """
    # Build library-level filters (source only)
    library_filters: Optional[RatingCoverageFilters] = None
    if source_filter and source_filter != "all":
        library_filters = {"source_filter": source_filter}

    # Build filter-level filters (all filters)
    filter_filters: Optional[RatingCoverageFilters] = None
    if library_filters or genre_filter or year_filter or playlist_id:
        filter_filters = library_filters.copy() if library_filters else {}
        if genre_filter:
            filter_filters["genre_filter"] = genre_filter
        if year_filter:
            filter_filters["year_filter"] = year_filter
        if playlist_id:
            filter_filters["playlist_id"] = playlist_id

    return library_filters, filter_filters


def _load_coverage_stats_for_session(
    source_filter: Optional[str],
    genre_filter: Optional[str],
    year_filter: Optional[int],
    playlist_id: Optional[int],
) -> tuple[
    RatingCoverageStats,
    RatingCoverageStats | None,
    RatingCoverageFilters | None,
    RatingCoverageFilters | None,
]:
    """Compute coverage stats for the library and active filter scope."""

    library_filters, filter_filters = _build_coverage_filter_sets(
        source_filter, genre_filter, year_filter, playlist_id
    )

    library_stats = get_ratings_coverage(library_filters)
    if filter_filters and filter_filters != library_filters:
        filter_stats = get_ratings_coverage(filter_filters)
    else:
        filter_filters = None
        filter_stats = None

    return library_stats, filter_stats, library_filters, filter_filters


def parse_rate_args(args: list[str]) -> dict:
    """
    Parse command line arguments for /rate command.

    Args:
        args: List of command line arguments

    Returns:
        Dict with 'count', 'playlist', 'genre', 'year', 'source' keys

    Examples:
        >>> parse_rate_args([])
        {'count': 15, 'playlist': None, 'genre': None, 'year': None, 'source': None}
        >>> parse_rate_args(['--count=30', '--genre=dubstep'])
        {'count': 30, 'playlist': None, 'genre': 'dubstep', 'year': None, 'source': None}
        >>> parse_rate_args(['--source=spotify'])
        {'count': 15, 'playlist': None, 'genre': None, 'year': None, 'source': 'spotify'}
    """
    parsed = {
        "count": 15,  # Default count
        "playlist": None,
        "genre": None,
        "year": None,
        "source": None,
    }

    for arg in args:
        if "=" not in arg:
            continue

        key, value = arg.split("=", 1)
        key = key.lstrip("-")  # Remove -- prefix

        if key == "count":
            try:
                parsed["count"] = int(value)
            except ValueError:
                logger.warning(f"Invalid count value: {value}, using default 15")
                parsed["count"] = 15

        elif key == "playlist":
            try:
                parsed["playlist"] = int(value)
            except ValueError:
                logger.warning(f"Invalid playlist ID: {value}")
                parsed["playlist"] = None

        elif key == "genre":
            parsed["genre"] = value

        elif key == "year":
            try:
                parsed["year"] = int(value)
            except ValueError:
                logger.warning(f"Invalid year value: {value}")
                parsed["year"] = None

        elif key == "source":
            valid_sources = ["local", "spotify", "soundcloud", "youtube", "all"]
            if value in valid_sources:
                parsed["source"] = value
            else:
                logger.warning(
                    f"Invalid source value: {value}. "
                    f"Must be one of: {', '.join(valid_sources)}"
                )
                parsed["source"] = None

    return parsed


def handle_rate_history_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Show rating history viewer with recent ratings.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.core.database import get_rating_history

    # Load rating history from database
    try:
        ratings = get_rating_history(limit=100)
    except Exception as e:
        logger.exception("Error loading rating history")
        log(f"Error loading rating history: {e}", level="error")
        return ctx, True

    # Handle empty results
    if not ratings:
        log("No ratings found.", level="warning")
        return ctx, True

    # If in blessed UI mode with update callback, show in viewer
    if ctx.ui_mode == "blessed" and ctx.update_ui_state:
        ctx = ctx.with_ui_action(
            {
                "type": "show_rating_history",
                "ratings": ratings,
            }
        )
        return ctx, True

    # Fallback: CLI mode - show ratings as text
    log(f"📋 Rating History ({len(ratings)} ratings)", level="info")
    log("", level="info")

    for rating in ratings[:20]:  # Show first 20 in CLI mode
        rating_type = rating.get("rating_type", "unknown")
        timestamp = rating.get("timestamp", "")
        artist = rating.get("artist", "Unknown")
        title = rating.get("title", "Unknown")

        # Format timestamp
        from datetime import datetime

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            time_str = timestamp[:19] if timestamp else ""

        # Rating type icon
        type_icons = {
            "like": "👍",
            "love": "❤️",
            "archive": "📦",
            "skip": "⏭️",
        }
        icon = type_icons.get(rating_type, "⭐")

        log(f"{icon} {rating_type:<7} • {artist} - {title} • {time_str}", level="info")

    if len(ratings) > 20:
        log("", level="info")
        log(
            f"  ... and {len(ratings) - 20} more (use blessed UI for full history)",
            level="info",
        )

    return ctx, True


def handle_rate_comparisons_command(ctx: AppContext) -> tuple[AppContext, bool]:
    """Show comparison history viewer with recent Elo comparisons.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.domain.rating.database import get_recent_comparisons

    # Load comparison history from database
    try:
        comparisons = get_recent_comparisons(limit=100)
    except Exception as e:
        logger.exception("Error loading comparison history")
        log(f"Error loading comparison history: {e}", level="error")
        return ctx, True

    # Handle empty results
    if not comparisons:
        log(
            "No comparisons found. Run 'rate' to start comparing tracks.",
            level="warning",
        )
        return ctx, True

    # If in blessed UI mode with update callback, show in viewer
    if ctx.ui_mode == "blessed" and ctx.update_ui_state:
        ctx = ctx.with_ui_action(
            {
                "type": "show_comparison_history",
                "comparisons": comparisons,
            }
        )
        return ctx, True

    # Fallback: CLI mode - show comparisons as text
    log(f"🏆 Comparison History ({len(comparisons)} comparisons)", level="info")
    log("", level="info")

    for comparison in comparisons[:20]:  # Show first 20 in CLI mode
        track_a_title = comparison.get("track_a_title", "Unknown")
        track_a_artist = comparison.get("track_a_artist", "Unknown")
        track_b_title = comparison.get("track_b_title", "Unknown")
        track_b_artist = comparison.get("track_b_artist", "Unknown")
        winner_id = comparison.get("winner_id")
        track_a_id = comparison.get("track_a_id")
        timestamp = comparison.get("timestamp", "")

        # Format timestamp
        from datetime import datetime

        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            time_str = timestamp[:19] if timestamp else ""

        # Determine winner
        if winner_id == track_a_id:
            winner_str = f"{track_a_artist} - {track_a_title}"
            loser_str = f"{track_b_artist} - {track_b_title}"
        else:
            winner_str = f"{track_b_artist} - {track_b_title}"
            loser_str = f"{track_a_artist} - {track_a_title}"

        log(f"🏆 {winner_str} > {loser_str} • {time_str}", level="info")

    if len(comparisons) > 20:
        log("", level="info")
        log(
            f"  ... and {len(comparisons) - 20} more (use blessed UI for full history)",
            level="info",
        )

    return ctx, True


def handle_rate_command(
    ctx: AppContext, cmd: str, args: list[str]
) -> tuple[AppContext, bool]:
    """
    Start a pairwise comparison rating session or show history.

    Command usage:
        /rate                              # 15 comparisons, active library tracks
        /rate history                      # Show like/love/archive rating history
        /rate comparisons                  # Show Elo comparison history
        /rate --count=30                   # 30 comparisons
        /rate --source=local               # Only local tracks
        /rate --source=spotify             # Only Spotify tracks
        /rate --source=all                 # All tracks regardless of source
        /rate --playlist=ID                # Only tracks in playlist
        /rate --genre=dubstep              # Only dubstep tracks
        /rate --year=2025                  # Only 2025 tracks
        /rate --genre=dubstep --year=2025  # Combined filters

    Args:
        ctx: Application context
        cmd: Command string (unused)
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    import threading

    from music_minion.core.database import get_active_provider
    from music_minion.ui.blessed.state import ComparisonState

    # Check for "history" subcommand (like/love/archive ratings)
    if args and args[0] == "history":
        return handle_rate_history_command(ctx)

    # Check for "comparisons" subcommand (Elo comparison decisions)
    if args and args[0] == "comparisons":
        return handle_rate_comparisons_command(ctx)

    # Parse arguments
    parsed = parse_rate_args(args)
    count = parsed["count"]
    playlist_id = parsed["playlist"]
    genre_filter = parsed["genre"]
    year_filter = parsed["year"]
    source_filter = parsed.get("source")  # May be None if not specified

    # Auto-detect active library if not specified via --source
    if not source_filter:
        source_filter = get_active_provider()

    logger.info(
        f"Starting rating session: count={count}, playlist={playlist_id}, "
        f"genre={genre_filter}, year={year_filter}, source={source_filter}"
    )

    # If in blessed UI mode with update callback, use progressive enhancement
    if ctx.ui_mode == "blessed" and ctx.update_ui_state:
        # Save current playback state
        saved_state = ctx.player_state

        # Generate session ID
        session_id = str(uuid.uuid4())

        library_filters, filter_filters = _build_coverage_filter_sets(
            source_filter, genre_filter, year_filter, playlist_id
        )

        # Create loading comparison state (shown immediately)
        loading_comparison = ComparisonState(
            active=True,
            loading=True,  # Show loading skeleton
            highlighted="a",
            session_id=session_id,
            comparisons_done=0,
            target_comparisons=count,
            playlist_id=playlist_id,
            genre_filter=genre_filter,
            year_filter=year_filter,
            source_filter=source_filter,
            session_start=datetime.now(),
            saved_player_state=saved_state,
            coverage_library_filters=library_filters,
            coverage_filter_filters=filter_filters,
        )

        # Update UI immediately with loading state
        ctx = ctx.with_ui_action(
            {
                "type": "start_comparison",
                "comparison": loading_comparison,
            }
        )

        # Start background thread to load data
        thread = threading.Thread(
            target=_load_comparison_data_background,
            args=(
                ctx,
                session_id,
                count,
                source_filter,
                genre_filter,
                year_filter,
                playlist_id,
                saved_state,
            ),
            daemon=True,
        )
        thread.start()

        return ctx, True

    # Fallback: CLI mode or no update callback - load synchronously
    else:
        from music_minion.domain.rating.database import get_filtered_tracks
        from music_minion.domain.rating.elo import select_strategic_pair

        # Load and filter tracks
        try:
            tracks = get_filtered_tracks(
                genre=genre_filter,
                year=year_filter,
                playlist_id=playlist_id,
                source_filter=source_filter,
            )
        except Exception as e:
            logger.exception("Failed to load tracks for rating session")
            log(f"❌ Failed to load tracks: {e}", level="error")
            return ctx, True

        # Validate track count
        if len(tracks) < 2:
            filter_desc = []
            if source_filter and source_filter != "all":
                filter_desc.append(f"source={source_filter}")
            if genre_filter:
                filter_desc.append(f"genre={genre_filter}")
            if year_filter:
                filter_desc.append(f"year={year_filter}")
            if playlist_id:
                filter_desc.append(f"playlist={playlist_id}")

            filter_str = " with " + ", ".join(filter_desc) if filter_desc else ""
            log(
                f"❌ Need at least 2 tracks for comparison{filter_str}. Found {len(tracks)}.",
                level="warning",
            )
            return ctx, True

        # Build ratings cache for strategic pairing
        ratings_cache = {
            track["id"]: {
                "rating": track["rating"],
                "comparison_count": track["comparison_count"],
            }
            for track in tracks
        }

        # Select first pair using strategic pairing
        try:
            track_a, track_b = select_strategic_pair(tracks, ratings_cache)
        except ValueError as e:
            logger.exception("Failed to select strategic pair")
            log(f"❌ Failed to select tracks: {e}", level="error")
            return ctx, True

        # Generate session ID
        session_id = str(uuid.uuid4())

        (
            library_stats,
            filter_stats,
            library_filters,
            filter_filters,
        ) = _load_coverage_stats_for_session(
            source_filter, genre_filter, year_filter, playlist_id
        )

        # Initialize comparison session
        comparison = ComparisonState(
            active=True,
            loading=False,
            track_a=track_a,
            track_b=track_b,
            highlighted="a",
            session_id=session_id,
            comparisons_done=0,
            target_comparisons=count,
            playlist_id=playlist_id,
            genre_filter=genre_filter,
            year_filter=year_filter,
            source_filter=source_filter,
            session_start=datetime.now(),
            saved_player_state=None,
            filtered_tracks=tracks,
            ratings_cache=ratings_cache,
            coverage_library_stats=library_stats,
            coverage_filter_stats=filter_stats,
            coverage_library_filters=library_filters,
            coverage_filter_filters=filter_filters,
        )

        # Log session start
        filter_parts = []
        if source_filter and source_filter != "all":
            filter_parts.append(f"{source_filter}")
        if genre_filter:
            filter_parts.append(f"genre={genre_filter}")
        if year_filter:
            filter_parts.append(f"year={year_filter}")
        if playlist_id:
            filter_parts.append(f"playlist={playlist_id}")

        filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""
        log(
            f"🎵 Starting rating session: {count} comparisons, "
            f"{len(tracks)} tracks{filter_desc}",
            level="info",
        )

        # Update context with UI action to start comparison mode
        ctx = ctx.with_ui_action(
            {
                "type": "start_comparison",
                "comparison": comparison,
            }
        )

        return ctx, True
