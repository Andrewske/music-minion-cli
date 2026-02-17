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
    get_playlist_leaderboard,
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
    result = {"limit": 50, "genre": None, "year": None, "playlist": None}

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
        elif arg.startswith("--playlist="):
            try:
                result["playlist"] = int(arg.split("=", 1)[1])
            except ValueError:
                logger.warning(f"Invalid playlist ID: {arg}")

    return result


def handle_rankings_command(
    ctx: AppContext, args: list[str]
) -> tuple[AppContext, bool]:
    """Display top-rated tracks in command palette.

    Args:
        ctx: Application context
        args: Command arguments (--genre=X, --year=Y, --playlist=ID, --limit=N)

    Returns:
        (updated_context, should_continue)

    Examples:
        rankings                    # Top 50 tracks globally
        rankings --genre=dubstep    # Top dubstep tracks
        rankings --year=2025        # Top 2025 tracks
        rankings --playlist=123     # Top tracks in playlist 123
        rankings --limit=100        # Top 100 tracks
    """
    from music_minion.domain.rating.database import get_leaderboard

    # Parse arguments
    parsed = parse_rankings_args(args)

    # Load leaderboard from database
    try:
        if parsed["playlist"] is not None:
            # Use playlist-specific rankings
            tracks = get_playlist_leaderboard(
                playlist_id=parsed["playlist"],
                limit=parsed["limit"],
                min_comparisons=1,
            )
        else:
            # Use global rankings
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
    if parsed["playlist"] is not None:
        # Get playlist name for title
        from music_minion.domain.playlists.crud import get_playlist_by_id

        playlist = get_playlist_by_id(parsed["playlist"])
        if playlist:
            title = f"Playlist Rankings: {playlist['name']}"
        else:
            title = f"Playlist Rankings: ID {parsed['playlist']}"
    elif parsed["genre"] or parsed["year"]:
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


def parse_rate_args(args: list[str]) -> dict:
    """
    Parse command line arguments for /rate command.

    Args:
        args: List of command line arguments

    Returns:
        Dict with 'playlist', 'genre', 'year', 'source' keys

    Examples:
        >>> parse_rate_args([])
        {'playlist': None, 'genre': None, 'year': None, 'source': None}
        >>> parse_rate_args(['--genre=dubstep'])
        {'playlist': None, 'genre': 'dubstep', 'year': None, 'source': None}
        >>> parse_rate_args(['--source=spotify'])
        {'playlist': None, 'genre': None, 'year': None, 'source': 'spotify'}
    """
    parsed = {
        "playlist": None,
        "playlist_rank": None,
        "genre": None,
        "year": None,
        "source": None,
    }

    for arg in args:
        if "=" not in arg:
            continue

        key, value = arg.split("=", 1)
        key = key.lstrip("-")  # Remove -- prefix

        if key == "playlist":
            try:
                parsed["playlist"] = int(value)
            except ValueError:
                logger.warning(f"Invalid playlist ID: {value}")
                parsed["playlist"] = None

        elif key == "playlist-rank":
            try:
                parsed["playlist_rank"] = int(value)
            except ValueError:
                logger.warning(f"Invalid playlist ID for ranking: {value}")
                parsed["playlist_rank"] = None

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


def handle_playlist_ranking_command(
    ctx: AppContext, playlist_id: int
) -> tuple[AppContext, bool]:
    """
    Handle playlist ranking command - start playlist-specific ELO ranking session.

    Args:
        ctx: Application context
        playlist_id: ID of playlist to rank

    Returns:
        (updated_context, should_continue)
    """
    from music_minion.domain.playlists.crud import get_playlist_by_id
    from music_minion.domain.rating.database import (
        RankingComplete,
        get_next_playlist_pair,
        get_playlist_comparison_progress,
    )
    from music_minion.ui.blessed.state import ComparisonState

    # Verify playlist exists
    playlist = get_playlist_by_id(playlist_id)
    if not playlist:
        log(f"❌ Playlist with ID {playlist_id} not found", level="error")
        return ctx, True

    # Get progress stats (stateless)
    progress = get_playlist_comparison_progress(playlist_id)
    comparisons_done = progress["compared"]

    # If in blessed UI mode, start comparison interface
    if ctx.ui_mode == "blessed" and ctx.update_ui_state:
        # Get first pair (stateless)
        try:
            track_a, track_b = get_next_playlist_pair(playlist_id)
        except RankingComplete:
            log("Playlist ranking already complete!", level="info")
            return ctx, True
        except ValueError as e:
            log(str(e), level="error")
            return ctx, True

        # Create comparison state for playlist ranking
        comparison = ComparisonState(
            active=True,
            loading=False,
            highlighted="a",
            comparisons_done=comparisons_done,
            playlist_id=playlist_id,
            track_a=track_a,
            track_b=track_b,
        )

        log(
            f"🎵 Starting playlist ranking for '{playlist['name']}' "
            f"({comparisons_done}/{progress['total']} comparisons done)",
            level="info",
        )

        # Update context with UI action to start comparison mode
        ctx = ctx.with_ui_action(
            {
                "type": "start_playlist_ranking",
                "comparison": comparison,
            }
        )

        return ctx, True

    else:
        log("❌ Playlist ranking requires blessed UI mode", level="error")
        return ctx, True


def handle_rate_command(
    ctx: AppContext, cmd: str, args: list[str]
) -> tuple[AppContext, bool]:
    """
    Start a pairwise comparison rating session or show history.

    Command usage:
        /rate history                      # Show like/love/archive rating history
        /rate comparisons                  # Show Elo comparison history
        /rate --playlist=ID                # Rank tracks within playlist (playlist-specific ratings)

    Args:
        ctx: Application context
        cmd: Command string (unused)
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    # Check for "history" subcommand (like/love/archive ratings)
    if args and args[0] == "history":
        return handle_rate_history_command(ctx)

    # Check for "comparisons" subcommand (Elo comparison decisions)
    if args and args[0] == "comparisons":
        return handle_rate_comparisons_command(ctx)

    # Parse arguments
    parsed = parse_rate_args(args)
    playlist_id = parsed["playlist"]

    # Only playlist-based comparison supported now
    if playlist_id is not None:
        return handle_playlist_ranking_command(ctx, playlist_id)

    # Global comparisons removed - use playlists instead
    log("❌ Global comparisons removed. Use /rate --playlist=ID instead.", level="error")
    log("   To rank all tracks, create an 'All' playlist first.", level="info")
    return ctx, True
