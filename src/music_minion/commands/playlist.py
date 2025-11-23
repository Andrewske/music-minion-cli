"""
Playlist command handlers for Music Minion CLI.

Handles: playlist list, playlist new, playlist delete, playlist rename,
         playlist show, playlist active, playlist import, playlist export
"""

import shlex
import sys
from pathlib import Path
from typing import List, Tuple

from music_minion import helpers
from music_minion.context import AppContext
from music_minion.core import config, database
from music_minion.core.output import log
from music_minion.domain import ai, library, playback, playlists
from music_minion.domain.playlists import ai_parser as playlist_ai
from music_minion.domain.playlists import analytics as playlist_analytics
from music_minion.domain.playlists import exporters as playlist_export
from music_minion.domain.playlists import filters as playlist_filters
from music_minion.domain.playlists import importers as playlist_import


def handle_playlist_list_command(ctx: AppContext) -> Tuple[AppContext, bool]:
    """
    Handle playlist command - signal UI to show playlist palette.

    Args:
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Get active library from database
    with database.get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        active_library = row["provider"] if row else "local"

    # Check if there are any playlists (filtered by active library)
    all_playlists = playlists.get_playlists_sorted_by_recent(library=active_library)

    if not all_playlists:
        log(
            "No playlists found. Create one with: playlist new manual <name>",
            level="info",
        )
        return ctx, True

    # Signal UI to show playlist palette
    ctx = ctx.with_ui_action({"type": "show_playlist_palette"})
    return ctx, True


def smart_playlist_wizard(name: str, ctx: AppContext) -> Tuple[AppContext, bool]:
    """Interactive wizard for creating a smart playlist with filters.

    Args:
        name: Name of the playlist to create
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Check if running in blessed UI mode (stdout is redirected)
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        log("❌ Interactive wizard not available in blessed UI mode", level="error")
        log(
            f'   Use AI wizard instead: playlist new smart ai {name} "<description>"',
            level="info",
        )
        log(
            '   Example: playlist new smart ai NYE2025 "dubstep from 2025 with bpm > 140"',
            level="info",
        )
        return ctx, True

    log(f"\n🧙 Smart Playlist Wizard: {name}", level="info")
    log("=" * 60, level="info")
    log("Create filters to automatically match tracks.\n", level="info")

    # Create the playlist first
    try:
        playlist_id = playlists.create_playlist(name, "smart", description=None)
    except ValueError as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True

    filters_added = []

    # Loop to add filters
    while True:
        log("\n" + "-" * 60, level="info")
        log("Add a filter rule:", level="info")
        log("", level="info")

        # Show valid fields
        log("Available fields:", level="info")
        log("  Text: title, artist, album, genre, key", level="info")
        log("  Numeric: year, bpm", level="info")
        log("", level="info")

        # Get field
        field = input("Field (or 'done' to finish): ").strip().lower()

        if field == "done":
            if not filters_added:
                log(
                    "❌ You must add at least one filter for a smart playlist",
                    level="error",
                )
                # Delete the empty playlist
                playlists.delete_playlist(playlist_id)
                return ctx, True
            break

        if field not in playlist_filters.VALID_FIELDS:
            log(
                f"❌ Invalid field. Must be one of: {', '.join(sorted(playlist_filters.VALID_FIELDS))}",
                level="error",
            )
            continue

        # Show valid operators for this field
        if field in playlist_filters.NUMERIC_FIELDS:
            log(
                f"\nNumeric operators: {', '.join(sorted(playlist_filters.NUMERIC_OPERATORS))}",
                level="info"
            )
            valid_ops = playlist_filters.NUMERIC_OPERATORS
        else:
            log(
                f"\nText operators: {', '.join(sorted(playlist_filters.TEXT_OPERATORS))}",
                level="info"
            )
            valid_ops = playlist_filters.TEXT_OPERATORS

        # Get operator
        operator = input("Operator: ").strip().lower()

        if operator not in valid_ops:
            log(
                f"❌ Invalid operator for {field}. Must be one of: {', '.join(sorted(valid_ops))}",
                level="error",
            )
            continue

        # Get value
        value = input("Value: ").strip()

        if not value:
            log("❌ Value cannot be empty", level="error")
            continue

        # Determine conjunction for next filter
        conjunction = "AND"
        if filters_added:
            conj_input = (
                input("Combine with previous filter using AND or OR? [AND]: ")
                .strip()
                .upper()
            )
            if conj_input in ("AND", "OR"):
                conjunction = conj_input

        # Add filter
        try:
            filter_id = playlist_filters.add_filter(
                playlist_id, field, operator, value, conjunction
            )
            filters_added.append(
                {
                    "id": filter_id,
                    "field": field,
                    "operator": operator,
                    "value": value,
                    "conjunction": conjunction,
                }
            )
            log(f"✅ Added filter: {field} {operator} '{value}'", level="info")
        except ValueError as e:
            log(f"❌ Error: {e}", level="error")
            continue

        # Ask if they want to add another
        more = input("\nAdd another filter? (y/n) [n]: ").strip().lower()
        if more != "y":
            break

    # Preview matching tracks
    log("\n" + "=" * 60, level="info")
    log("📊 Preview: Finding matching tracks...", level="info")

    try:
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)
        count = len(matching_tracks)

        log(f"\n✅ Found {count} matching tracks", level="info")

        if count > 0:
            log("\nFirst 10 matches:", level="info")
            for i, track in enumerate(matching_tracks[:10], 1):
                artist = track.get("artist", "Unknown")
                title = track.get("title", "Unknown")
                album = track.get("album", "")
                log(f"  {i}. {artist} - {title}", level="info")
                if album:
                    log(f"     Album: {album}", level="info")

        # Show filters
        log(f"\n📋 Filter rules for '{name}':", level="info")
        for i, f in enumerate(filters_added, 1):
            prefix = f"  {f['conjunction']}" if i > 1 else "  "
            log(f"{prefix} {f['field']} {f['operator']} '{f['value']}'", level="info")

        # Confirm
        log("", level="info")
        confirm = input("Save this smart playlist? (y/n) [y]: ").strip().lower()

        if confirm == "n":
            playlists.delete_playlist(playlist_id)
            log("❌ Smart playlist cancelled", level="warning")
            return ctx, True

        # Update track count for the smart playlist
        playlists.update_playlist_track_count(playlist_id)

        log(f"\n✅ Created smart playlist: {name}", level="info")
        log(f"   {count} tracks match your filters", level="info")
        log(f'   Set as active with: playlist active "{name}"', level="info")

        # Auto-export if enabled
        helpers.auto_export_if_enabled(playlist_id)

    except Exception as e:
        log(f"❌ Error evaluating filters: {e}", level="error")
        playlists.delete_playlist(playlist_id)
        return ctx, True

    return ctx, True


def validate_filters_list(filters: List[playlist_ai.FilterDict]) -> List[str]:
    """Validate all filters and return list of error messages.

    Args:
        filters: List of filter dictionaries to validate

    Returns:
        List of validation error messages (empty if all valid)
    """
    validation_errors = []
    for i, f in enumerate(filters, 1):
        try:
            playlist_filters.validate_filter(f["field"], f["operator"], f["value"])
        except ValueError as e:
            validation_errors.append(f"Filter {i}: {e}")
    return validation_errors


def ai_smart_playlist_wizard(
    name: str, description: str, ctx: AppContext
) -> Tuple[AppContext, bool]:
    """AI-powered wizard for creating a smart playlist from natural language.

    Args:
        name: Name of the playlist to create
        description: Natural language description of desired playlist
        ctx: Application context

    Returns:
        (updated_context, should_continue)
    """
    # Check if running in blessed UI mode (stdout is redirected)
    is_blessed_mode = not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty()

    # Check API key early before doing anything
    if not ai.get_api_key():
        log(
            "❌ No OpenAI API key found. Use 'ai setup <key>' to configure.",
            level="error",
        )
        return ctx, True

    log(f"\n🤖 AI Smart Playlist Wizard: {name}", level="info")
    log("=" * 60, level="info")
    log(f'Description: "{description}"', level="info")
    log("\n🧠 Parsing with AI...", level="info")

    # Parse description with AI
    try:
        filters, metadata = playlist_ai.parse_natural_language_to_filters(description)
        log(f"✅ Parsed in {metadata['response_time_ms']}ms", level="info")
        log(
            f"   Tokens: {metadata['prompt_tokens']} prompt + {metadata['completion_tokens']} completion",
            level="info",
        )

        # Calculate and display estimated cost
        cfg = config.load_config()
        cost = (
            metadata["prompt_tokens"] * cfg.ai.cost_per_1m_input_tokens / 1_000_000
            + metadata["completion_tokens"]
            * cfg.ai.cost_per_1m_output_tokens
            / 1_000_000
        )
        log(f"   Estimated cost: ${cost:.6f}", level="info")
    except ai.AIError as e:
        log(f"❌ AI Error: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True

    # Validate all filters
    log("\n🔍 Validating filters...", level="info")
    validation_errors = validate_filters_list(filters)

    if validation_errors:
        log("❌ Validation errors found:", level="error")
        for error in validation_errors:
            log(f"   {error}", level="error")
        log("\n⚠️  AI generated invalid filters. Please try:", level="warning")
        log("   1. Use simpler description", level="info")
        log(
            f'   2. Use manual filter wizard: playlist new smart "{name}"', level="info"
        )
        return ctx, True

    log(f"✅ All {len(filters)} filters are valid", level="info")

    # Show parsed filters
    log("\n📋 Parsed filters:", level="info")
    log(playlist_ai.format_filters_for_preview(filters), level="info")

    # Ask if user wants to edit (skip in blessed mode)
    edit = "n"
    if not is_blessed_mode:
        log("\n" + "=" * 60, level="info")
        edit = (
            input("Edit filters before creating playlist? (y/n) [n]: ").strip().lower()
        )

    if edit == "y":
        try:
            filters = playlist_ai.edit_filters_interactive(filters)
        except KeyboardInterrupt:
            log("\n❌ Cancelled", level="warning")
            return ctx, True

        # Check if filters are empty after editing
        if not filters:
            log(
                "❌ No filters remaining. Cannot create empty smart playlists.",
                level="error",
            )
            return ctx, True

        # Re-validate after editing
        validation_errors = validate_filters_list(filters)

        if validation_errors:
            log("❌ Validation errors after editing:", level="error")
            for error in validation_errors:
                log(f"   {error}", level="error")
            return ctx, True

    # Create playlist
    log("\n" + "=" * 60, level="info")
    log(f"Creating smart playlist: {name}", level="info")

    try:
        playlist_id = playlists.create_playlist(name, "smart", description=description)
    except ValueError as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True

    # Add all filters
    try:
        for f in filters:
            playlist_filters.add_filter(
                playlist_id,
                f["field"],
                f["operator"],
                f["value"],
                f.get("conjunction", "AND"),
            )
    except Exception as e:
        log(f"❌ Error adding filters: {e}", level="error")
        playlists.delete_playlist(playlist_id)
        return ctx, True

    # Preview matching tracks
    log("\n📊 Preview: Finding matching tracks...", level="info")

    try:
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)
        count = len(matching_tracks)

        log(f"\n✅ Found {count} matching tracks", level="info")

        if count > 0:
            log("\nFirst 10 matches:", level="info")
            for i, track in enumerate(matching_tracks[:10], 1):
                artist = track.get("artist", "Unknown")
                title = track.get("title", "Unknown")
                album = track.get("album", "")
                log(f"  {i}. {artist} - {title}", level="info")
                if album:
                    log(f"     Album: {album}", level="info")

        # Show final filters
        log(f"\n📋 Filter rules for '{name}':", level="info")
        for i, f in enumerate(filters, 1):
            prefix = f"  {f['conjunction']}" if i > 1 else "  "
            log(f"{prefix} {f['field']} {f['operator']} '{f['value']}'", level="info")

        # Confirm (skip in blessed mode, default to yes)
        confirm = "y"
        if not is_blessed_mode:
            log("", level="info")
            confirm = input("Save this smart playlist? (y/n) [y]: ").strip().lower()

        if confirm == "n":
            playlists.delete_playlist(playlist_id)
            log("❌ Smart playlist cancelled", level="warning")
            return ctx, True

        log(f"\n✅ Created AI smart playlist: {name}", level="info")
        log(f"   {count} tracks match your filters", level="info")
        log(f"   Description: {description}", level="info")
        log(f'   Set as active with: playlist active "{name}"', level="info")

        # Auto-export if enabled
        helpers.auto_export_if_enabled(playlist_id)

    except Exception as e:
        log(f"❌ Error evaluating filters: {e}", level="error")
        playlists.delete_playlist(playlist_id)
        return ctx, True

    return ctx, True


def handle_playlist_new_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist new command - create a new playlists.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if len(args) < 2:
        log("Error: Please specify playlist type and name", level="error")
        log("Usage: playlist new manual <name>", level="info")
        log("       playlist new smart <name>", level="info")
        log('       playlist new smart ai <name> "<description>"', level="info")
        return ctx, True

    playlist_type = args[0].lower()
    if playlist_type not in ["manual", "smart"]:
        log(
            f"Error: Invalid playlist type '{playlist_type}'. Must be 'manual' or 'smart'",
            level="error",
        )
        return ctx, True

    # Check for AI smart playlist
    if playlist_type == "smart" and len(args) >= 2 and args[1].lower() == "ai":
        # Format: smart ai <name> "<description>"
        # Need to parse name and quoted description
        if len(args) < 3:
            log("Error: Please specify playlist name and description", level="error")
            log('Usage: playlist new smart ai <name> "<description>"', level="info")
            return ctx, True

        # Use shlex for proper shell-like parsing
        try:
            # Join everything after 'ai' and parse with shlex
            rest = " ".join(args[2:])
            parts = shlex.split(rest)

            if len(parts) >= 2:
                name = parts[0]
                description = parts[1]
                return ai_smart_playlist_wizard(name, description, ctx)
            else:
                log("Error: Please provide both name and description", level="error")
                log('Usage: playlist new smart ai <name> "<description>"', level="info")
                log(
                    'Example: playlist new smart ai NYE2025 "all dubstep from 2025"',
                    level="info",
                )
                return ctx, True

        except ValueError as e:
            log(f"Error parsing command: {e}", level="error")
            log('Usage: playlist new smart ai <name> "<description>"', level="info")
            log(
                'Example: playlist new smart ai NYE2025 "all dubstep from 2025"',
                level="info",
            )
            return ctx, True

    # Regular smart playlist - launch blessed wizard via UI action
    if playlist_type == "smart":
        name = " ".join(args[1:])
        # Signal UI to start wizard
        ctx = ctx.with_ui_action(
            {
                "type": "start_wizard",
                "wizard_type": "smart_playlist",
                "wizard_data": {"name": name, "filters": []},
            }
        )
        return ctx, True

    # Manual playlist - assign name from remaining args
    name = " ".join(args[1:])

    try:
        playlist_id = playlists.create_playlist(name, playlist_type, description=None)
        log(f"✅ Created {playlist_type} playlist: {name}", level="info")
        log(f"   Playlist ID: {playlist_id}", level="info")
        log(f'   Add tracks with: add "{name}"', level="info")

        # Auto-export if enabled
        helpers.auto_export_if_enabled(playlist_id)

        return ctx, True
    except ValueError as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Error creating playlist: {e}", level="error")
        return ctx, True


def handle_playlist_delete_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist delete command - delete a playlists.

    Args:
        ctx: Application context
        args: Command arguments

    Returns:
        (updated_context, should_continue)
    """
    if not args:
        log("Error: Please specify playlist name", level="error")
        log("Usage: playlist delete <name>", level="info")
        return ctx, True

    name = " ".join(args)
    pl = playlists.get_playlist_by_name(name)

    if not pl:
        log(f"❌ Playlist '{name}' not found", level="error")
        return ctx, True

    # Confirm deletion
    log(f"⚠️  Delete playlist '{name}'? This cannot be undone.", level="warning")
    confirm = input("Type 'yes' to confirm: ").strip().lower()

    if confirm != "yes":
        log("Deletion cancelled", level="info")
        return ctx, True

    try:
        # Clear position tracking before deleting
        playback.clear_playlist_position(pl["id"])

        if playlists.delete_playlist(pl["id"]):
            log(f"✅ Deleted playlist: {name}", level="info")
        else:
            log(f"❌ Failed to delete playlist: {name}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Error deleting playlist: {e}", level="error")
        return ctx, True


def handle_playlist_rename_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist rename command - rename a playlists."""
    if len(args) < 2:
        log("Error: Please specify old and new names", level="error")
        log('Usage: playlist rename "old name" "new name"', level="info")
        return ctx, True

    # Parse quoted args to handle multi-word playlist names
    parsed_args = helpers.parse_quoted_args(args)

    if len(parsed_args) < 2:
        log("Error: Please specify both old and new names", level="error")
        log('Usage: playlist rename "old name" "new name"', level="info")
        return ctx, True

    old_name = parsed_args[0]
    new_name = parsed_args[1]

    pl = playlists.get_playlist_by_name(old_name)
    if not pl:
        log(f"❌ Playlist '{old_name}' not found", level="error")
        return ctx, True

    try:
        if playlists.rename_playlist(pl["id"], new_name):
            log(f"✅ Renamed playlist: '{old_name}' → '{new_name}'", level="info")
        else:
            log("❌ Failed to rename playlist", level="error")
        return ctx, True
    except ValueError as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Error renaming playlist: {e}", level="error")
        return ctx, True


def handle_playlist_show_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist show command - signal UI to show track viewer."""
    if not args:
        log("Error: Please specify playlist name", level="error")
        log("Usage: playlist show <name>", level="info")
        return ctx, True

    name = " ".join(args)
    pl = playlists.get_playlist_by_name(name)

    if not pl:
        log(f"❌ Playlist '{name}' not found", level="error")
        return ctx, True

    # Signal UI to show track viewer
    ctx = ctx.with_ui_action({"type": "show_track_viewer", "playlist_name": name})
    return ctx, True


def handle_playlist_active_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist active command - set or clear active playlists."""
    # Detect blessed UI mode (stdout redirected) - do this early
    is_blessed_mode = not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty()

    if not args:
        # Show current active playlist
        active = playlists.get_active_playlist()
        if active:
            log(f"Active playlist: {active['name']}", level="info")
        else:
            log("No active playlist (playing all tracks)", level="info")
        return ctx, True

    name = " ".join(args)

    if name.lower() == "none":
        # Clear active playlist
        # First get the active playlist ID to clear position tracking
        active = playlists.get_active_playlist()
        if active:
            playback.clear_playlist_position(active["id"])

        if playlists.clear_active_playlist():
            log("✅ Cleared active playlist (now playing all tracks)", level="info")
        else:
            log("No active playlist was set", level="info")
        return ctx, True

    # Set active playlist
    pl = playlists.get_playlist_by_name(name)
    if not pl:
        if not is_blessed_mode:
            log(f"❌ Playlist '{name}' not found", level="error")
        return ctx, True

    try:
        if playlists.set_active_playlist(pl["id"]):
            if not is_blessed_mode:
                log(f"✅ Set active playlist: {name}", level="info")
                log("   Now playing only tracks from this playlist", level="info")

            # Check if current track is in the new playlist
            current_track_id = ctx.player_state.current_track_id
            should_start_playback = True

            if current_track_id is not None:
                # Check if current track is in the new playlist
                playlist_tracks = playlists.get_playlist_tracks(pl["id"])
                track_ids_in_playlist = {track["id"] for track in playlist_tracks}

                if current_track_id in track_ids_in_playlist:
                    # Current track IS in new playlist - keep playing
                    should_start_playback = False
                    if not is_blessed_mode:
                        log(
                            "   Current track is in this playlist, continuing playback",
                            level="info",
                        )

            # Only start playback if current track is not in the new playlist
            if should_start_playback:
                # Check for saved position and shuffle mode
                saved_position = playback.get_playlist_position(pl["id"])
                shuffle_enabled = playback.get_shuffle_mode()

                # Sequential mode: offer to resume from saved position
                if saved_position and not shuffle_enabled:
                    track_id, position = saved_position
                    # Get playlist tracks to find the saved track
                    playlist_tracks = playlists.get_playlist_tracks(pl["id"])

                    # Find track info
                    saved_track = None
                    for track in playlist_tracks:
                        if track["id"] == track_id:
                            saved_track = track
                            break

                    if saved_track:
                        if not is_blessed_mode:
                            log(
                                f"\n💾 Last position: Track {position + 1}/{len(playlist_tracks)}",
                                level="info",
                            )
                            log(
                                f"   {saved_track.get('artist', 'Unknown')} - {saved_track.get('title', 'Unknown')}",
                                level="info",
                            )

                        # In blessed mode, auto-resume; otherwise prompt
                        if is_blessed_mode:
                            response = "y"  # Auto-resume in blessed UI
                        else:
                            response = (
                                input("   Resume from this position? [Y/n]: ")
                                .strip()
                                .lower()
                            )

                        if response != "n":
                            # Find the Track object from music_tracks
                            for track in ctx.music_tracks:
                                if track.local_path == saved_track["local_path"]:
                                    if not is_blessed_mode:
                                        log("▶️  Resuming playback...", level="info")
                                    # Import play_track from playback commands
                                    from . import playback as playback_commands

                                    ctx, _ = playback_commands.play_track(
                                        ctx, track, position
                                    )
                                    break

                # Shuffle mode: automatically start with random track
                elif shuffle_enabled:
                    # Import playback commands for helper functions
                    from . import playback as playback_commands

                    # Get available tracks from this playlist (excluding archived)
                    available_tracks = playback_commands.get_available_tracks(ctx)

                    if available_tracks:
                        if not is_blessed_mode:
                            log(
                                "\n🔀 Shuffle mode enabled - starting with random track",
                                level="info",
                            )
                            log(
                                f"   {len(available_tracks)} tracks available", level="info"
                            )

                        # Pick a random track from available
                        random_track = library.get_random_track(available_tracks)
                        if random_track:
                            if not is_blessed_mode:
                                log("▶️  Starting shuffle playback...", level="info")
                            ctx, _ = playback_commands.play_track(ctx, random_track)
                    else:
                        if not is_blessed_mode:
                            log(
                                "\n⚠️  No tracks available in this playlist (all may be archived)",
                                level="warning",
                            )

                # Sequential mode with no saved position - start from first track
                else:
                    # Import playback commands for helper functions
                    from . import playback as playback_commands

                    # Get playlist tracks
                    playlist_tracks = playlists.get_playlist_tracks(pl["id"])

                    if playlist_tracks:
                        # Get first track (position 0)
                        first_track_dict = playback.get_next_sequential_track(
                            playlist_tracks, None
                        )

                        if first_track_dict:
                            # Find the Track object from music_tracks
                            for track in ctx.music_tracks:
                                if track.local_path == first_track_dict["local_path"]:
                                    if not is_blessed_mode:
                                        log(
                                            "\n▶️  Starting from first track in playlist",
                                            level="info",
                                        )
                                        log(
                                            f"   {len(playlist_tracks)} tracks in playlist",
                                            level="info",
                                        )

                                    # Play track with position 0
                                    ctx, _ = playback_commands.play_track(ctx, track, 0)
                                    break
                        else:
                            if not is_blessed_mode:
                                log(
                                    "\n⚠️  Unable to find first track in playlist",
                                    level="warning",
                                )
                    else:
                        if not is_blessed_mode:
                            log("\n⚠️  Playlist is empty", level="warning")

        else:
            if not is_blessed_mode:
                log("❌ Failed to set active playlist", level="error")
        return ctx, True
    except Exception as e:
        if not is_blessed_mode:
            log(f"❌ Error setting active playlist: {e}", level="error")
        return ctx, True


def handle_playlist_restart_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """
    Handle playlist restart command - restart active playlist from first track.
    Turns off shuffle mode if enabled and clears any saved position.

    Args:
        ctx: Application context
        args: Command arguments (unused for restart)

    Returns:
        (updated_context, should_continue)
    """
    # Check if there's an active playlist
    active = playlists.get_active_playlist()
    if not active:
        log("⚠️  No active playlist set", level="warning")
        log("   Use 'playlist active <name>' to set one first", level="info")
        return ctx, True

    # Turn off shuffle mode if it's on
    shuffle_enabled = playback.get_shuffle_mode()
    if shuffle_enabled:
        playback.set_shuffle_mode(False)
        log("🔁 Shuffle mode disabled", level="info")

    # Clear saved playlist position
    playback.clear_playlist_position(active['id'])

    # Import playback commands for play_track
    from . import playback as playback_commands

    # Get playlist tracks
    playlist_tracks = playlists.get_playlist_tracks(active['id'])

    if not playlist_tracks:
        log(f"⚠️  Playlist '{active['name']}' is empty", level="warning")
        return ctx, True

    # Get first track (position 0)
    first_track_dict = playback.get_next_sequential_track(
        playlist_tracks, None
    )

    if not first_track_dict:
        log("❌ Unable to find first track in playlist", level="error")
        return ctx, True

    # Find the Track object from music_tracks using database ID
    first_track_id = first_track_dict.get('id')
    if not first_track_id:
        log("❌ First track has no database ID", level="error")
        return ctx, True

    # Query track directly from database instead of searching ctx.music_tracks
    db_track = database.get_track_by_id(first_track_id)
    if not db_track:
        log("❌ Track not found in database", level="error")
        return ctx, True

    # Convert database track to Track object
    track = database.db_track_to_library_track(db_track)

    log(f"🔄 Restarting playlist: {active['name']}", level="info")
    log(f"   {len(playlist_tracks)} tracks in playlist", level="info")

    # Play track with position 0
    ctx, _ = playback_commands.play_track(ctx, track, 0)
    return ctx, True


def handle_playlist_import_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist import command - import playlist from file."""
    current_config = ctx.config

    if not args:
        log("Error: Please specify playlist file path", level="error")
        log("Usage: playlist import <file>", level="info")
        log("Supported formats: .m3u, .m3u8, .crate", level="info")
        return ctx, True

    local_path_str = " ".join(args)
    local_path = Path(local_path_str).expanduser()

    if not local_path.exists():
        log(f"❌ File not found: {local_path}", level="error")
        return ctx, True

    # Get library root from config
    # Validate library paths exist
    if not current_config.music.library_paths:
        log("❌ Error: No library paths configured", level="error")
        return ctx, True
    library_root = Path(current_config.music.library_paths[0]).expanduser()

    # Auto-detect format and import
    try:
        format_type = playlist_import.detect_playlist_format(local_path)
        if not format_type:
            log(f"❌ Unsupported file format: {local_path.suffix}", level="error")
            log("Supported formats: .m3u, .m3u8, .crate", level="info")
            return ctx, True

        log(
            f"📂 Importing {format_type.upper()} playlist from: {local_path.name}",
            level="info",
        )

        playlist_id, tracks_added, duplicates_skipped, unresolved = (
            playlist_import.import_playlist(
                local_path=local_path,
                playlist_name=None,  # Use filename as default
                library_root=library_root,
            )
        )

        # Get the created playlist info
        pl = playlists.get_playlist_by_id(playlist_id)
        if pl:
            log(f"✅ Created playlist: {pl['name']}", level="info")
            log(f"   Tracks added: {tracks_added}", level="info")
            if duplicates_skipped > 0:
                log(f"   Duplicates skipped: {duplicates_skipped}", level="info")

            if unresolved:
                log(f"   ⚠️  Unresolved tracks: {len(unresolved)}", level="warning")
                if len(unresolved) <= 5:
                    log("\n   Could not find these tracks:", level="warning")
                    for path in unresolved:
                        # Show just filename for brevity
                        log(f"     • {Path(path).name}", level="warning")
                else:
                    log(
                        f"   Run 'playlist show {pl['name']}' to see details",
                        level="info",
                    )

            # Auto-export if enabled
            helpers.auto_export_if_enabled(playlist_id)

        return ctx, True

    except ValueError as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True
    except ImportError as e:
        log(f"❌ Missing dependency: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Error importing playlist: {e}", level="error")
        return ctx, True


def handle_playlist_export_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """Handle playlist export command - export playlist to file."""
    current_config = ctx.config

    if not args:
        log("Error: Please specify playlist name", level="error")
        log("Usage: playlist export <name> [format]", level="info")
        log("Formats: m3u8 (default), crate, all", level="info")
        return ctx, True

    # Parse arguments with smart format detection
    # Strategy: Try full name first, then try separating format
    format_type = "m3u8"  # Default format
    playlist_name = " ".join(args)

    # If more than one arg and last arg looks like a format, try separating
    if len(args) > 1 and args[-1].lower() in ["m3u8", "m3u", "crate", "all"]:
        # First check if the full name exists as a playlist
        pl_full = playlists.get_playlist_by_name(playlist_name)
        if not pl_full:
            # Full name doesn't exist, try separating the format
            potential_format = args[-1].lower()
            potential_name = " ".join(args[:-1])
            pl_separated = playlists.get_playlist_by_name(potential_name)
            if pl_separated:
                # Playlist exists without the last arg, treat it as format
                format_type = potential_format
                playlist_name = potential_name

    # Normalize format
    if format_type == "m3u":
        format_type = "m3u8"

    # Get library root from config
    # Validate library paths exist
    if not current_config.music.library_paths:
        log("❌ Error: No library paths configured", level="error")
        return ctx, True
    library_root = Path(current_config.music.library_paths[0]).expanduser()

    # Check if playlist exists
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        log(f"❌ Playlist '{playlist_name}' not found", level="error")
        return ctx, True

    try:
        if format_type == "all":
            # Export to both formats
            formats = ["m3u8", "crate"]
            log(
                f"📤 Exporting playlist '{playlist_name}' to all formats...",
                level="info",
            )

            for fmt in formats:
                try:
                    output_path, tracks_exported = playlist_export.export_playlist(
                        playlist_name=playlist_name,
                        format_type=fmt,
                        library_root=library_root,
                    )
                    log(
                        f"   ✅ {fmt.upper()}: {output_path} ({tracks_exported} tracks)",
                        level="info",
                    )
                except Exception as e:
                    log(f"   ❌ {fmt.upper()}: {e}", level="error")

        else:
            # Export to single format
            log(
                f"📤 Exporting playlist '{playlist_name}' to {format_type.upper()}...",
                level="info",
            )

            output_path, tracks_exported = playlist_export.export_playlist(
                playlist_name=playlist_name,
                format_type=format_type,
                library_root=library_root,
            )

            log(f"✅ Exported {tracks_exported} tracks to: {output_path}", level="info")

        return ctx, True

    except ValueError as e:
        log(f"❌ Error: {e}", level="error")
        return ctx, True
    except ImportError as e:
        log(f"❌ Missing dependency: {e}", level="error")
        return ctx, True
    except Exception as e:
        log(f"❌ Error exporting playlist: {e}", level="error")
        return ctx, True


def handle_playlist_analyze_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """
    Handle playlist analyze command - show comprehensive analytics.

    Usage:
      playlist analyze <name>                  - Full analytics report
      playlist analyze <name> --compact        - Compact summary
      playlist analyze <name> --section=<name> - Specific section only
    """
    if not args:
        log("Error: Please specify playlist name", level="error")
        log(
            "Usage: playlist analyze <name> [--compact] [--section=<name>]",
            level="info",
        )
        log(
            "Sections: basic, artists, genres, tags, bpm, keys, years, ratings, quality",
            level="info",
        )
        return ctx, True

    # Parse arguments
    compact_mode = "--compact" in args
    section_filter = None

    # Remove flags from args to get playlist name
    playlist_args = []
    for arg in args:
        if arg == "--compact":
            continue
        elif arg.startswith("--section="):
            section_filter = arg.split("=", 1)[1].strip()
        else:
            playlist_args.append(arg)

    if not playlist_args:
        log("Error: Please specify playlist name", level="error")
        return ctx, True

    playlist_name = " ".join(playlist_args)

    # Validate playlist exists
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        log(f"❌ Playlist '{playlist_name}' not found", level="error")
        return ctx, True

    # Validate section if specified
    valid_sections = [
        "basic",
        "artists",
        "genres",
        "tags",
        "bpm",
        "keys",
        "years",
        "ratings",
        "quality",
    ]
    if section_filter and section_filter not in valid_sections:
        log(f"❌ Invalid section: {section_filter}", level="error")
        log(f"Valid sections: {', '.join(valid_sections)}", level="info")
        return ctx, True

    # Get analytics
    try:
        sections_to_run = [section_filter] if section_filter else None
        analytics = playlist_analytics.get_playlist_analytics(
            pl["id"], sections=sections_to_run
        )

        if "error" in analytics:
            log(f"❌ Error: {analytics['error']}", level="error")
            return ctx, True

        # Show analytics in full-screen viewer
        ctx = ctx.with_ui_action(
            {"type": "show_analytics_viewer", "analytics_data": analytics}
        )
        return ctx, True
    except Exception as e:
        log(f"❌ Error analyzing playlist: {e}", level="error")
        import traceback

        traceback.print_exc()
        return ctx, True


def handle_playlist_convert_command(
    ctx: AppContext, args: List[str]
) -> Tuple[AppContext, bool]:
    """
    Handle playlist convert command - convert Spotify playlist to SoundCloud.

    Usage:
      playlist convert <spotify_playlist_name> <soundcloud_playlist_name>

    Args:
        ctx: Application context
        args: [spotify_name, soundcloud_name]

    Returns:
        (updated_context, should_continue)
    """
    from ..domain.playlists.conversion import convert_spotify_to_soundcloud

    if len(args) < 2:
        log("Error: Please specify both Spotify and SoundCloud playlist names", level="error")
        log('Usage: playlist convert "Spotify Name" "SoundCloud Name"', level="info")
        log('Example: playlist convert "Release Radar" "SC Release Radar"', level="info")
        return ctx, True

    # Parse quoted args
    parsed_args = helpers.parse_quoted_args(args)

    if len(parsed_args) < 2:
        log("Error: Please specify both playlist names", level="error")
        log('Usage: playlist convert "Spotify Name" "SoundCloud Name"', level="info")
        return ctx, True

    spotify_name = parsed_args[0]
    soundcloud_name = parsed_args[1]

    # Find Spotify playlist
    spotify_playlist = playlists.get_playlist_by_name(spotify_name, library='spotify')

    if not spotify_playlist:
        log(f"❌ Spotify playlist '{spotify_name}' not found", level="error")
        log("   Make sure you've synced your Spotify library first", level="info")
        return ctx, True

    # Check if it's actually a Spotify playlist
    if spotify_playlist.get("library") != "spotify":
        log(f"❌ '{spotify_name}' is not a Spotify playlist", level="error")
        log(f"   Library: {spotify_playlist.get('library', 'unknown')}", level="info")
        return ctx, True

    spotify_playlist_id = spotify_playlist.get("spotify_playlist_id")
    if not spotify_playlist_id:
        log(f"❌ Playlist '{spotify_name}' has no Spotify ID", level="error")
        return ctx, True

    # Progress callback for user feedback
    def progress_callback(current: int, total: int) -> None:
        percentage = (current / total * 100) if total > 0 else 0
        log(f"⏳ Matching tracks: {current}/{total} ({percentage:.0f}%)", level="info")

    # Run conversion
    log("\n🎵 Starting Spotify → SoundCloud conversion", level="info")
    log(f"   Source: {spotify_name}", level="info")
    log(f"   Target: {soundcloud_name}", level="info")
    log("", level="info")

    result = convert_spotify_to_soundcloud(
        spotify_playlist_id, soundcloud_name, progress_callback
    )

    # Report results
    log("\n" + "=" * 60, level="info")
    if result.success:
        log("✅ Conversion completed successfully!", level="info")
        log(f"   Total tracks: {result.total_tracks}", level="info")
        log(
            f"   Matched: {result.matched_tracks} ({result.matched_tracks / result.total_tracks * 100:.1f}%)",
            level="info",
        )

        if result.matched_tracks > 0:
            log(
                f"   Average confidence: {result.average_confidence:.2f}",
                level="info",
            )

        if result.soundcloud_playlist_url:
            log(f"   Playlist URL: {result.soundcloud_playlist_url}", level="info")

        if result.failed_tracks > 0:
            log(
                f"\n⚠️  {result.failed_tracks} tracks could not be matched:",
                level="warning",
            )
            for track_name in result.unmatched_track_names[:10]:
                log(f"     • {track_name}", level="warning")

            if len(result.unmatched_track_names) > 10:
                log(
                    f"     ... and {len(result.unmatched_track_names) - 10} more",
                    level="warning",
                )
    else:
        log("❌ Conversion failed", level="error")
        if result.error_message:
            log(f"   Error: {result.error_message}", level="error")

    log("=" * 60, level="info")

    return ctx, True
