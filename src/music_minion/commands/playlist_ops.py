"""
Playlist command handlers for Music Minion CLI.

Handles: playlist list, playlist new, playlist delete, playlist rename,
         playlist show, playlist active, playlist import, playlist export
"""

import shlex
import sys
from pathlib import Path
from typing import List

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

from ..core import config
from ..core import database
from ..domain import library
from ..domain import playback
from .. import ai
from .. import ui
from ..domain import playlists
from ..domain.playlists import filters as playlist_filters
from ..domain.playlists import ai_parser as playlist_ai
from ..domain.playlists import importers as playlist_import
from ..domain.playlists import exporters as playlist_export
from .. import completers


def get_player_state() -> playback.PlayerState:
    """Get current player state from main module."""
    from .. import main
    return main.current_player_state


def get_music_tracks() -> List[library.Track]:
    """Get music tracks from main module."""
    from .. import main
    return main.music_tracks


def get_config() -> config.Config:
    """Get current config from main module."""
    from .. import main
    return main.current_config


def safe_print(message: str, style: str = None) -> None:
    """Print using Rich Console if available."""
    from .. import main
    return main.safe_print(message, style)


def parse_quoted_args(args: List[str]) -> List[str]:
    """Parse command arguments respecting quoted strings."""
    from .. import main
    return main.parse_quoted_args(args)


def play_track(track: library.Track, playlist_position: int = None) -> bool:
    """Play a specific track."""
    from .. import main
    return main.play_track(track, playlist_position)


def ensure_library_loaded() -> bool:
    """Ensure music library is loaded."""
    from .. import main
    return main.ensure_library_loaded()


def auto_export_if_enabled(playlist_id: int) -> None:
    """
    Auto-export a playlist if auto-export is enabled in config.

    Args:
        playlist_id: ID of the playlist to export
    """
    current_config = get_config()

    if not current_config.playlists.auto_export:
        return

    # Validate library paths exist
    if not current_config.music.library_paths:
        print("Warning: Cannot auto-export - no library paths configured", file=sys.stderr)
        return

    # Get library root from config
    library_root = Path(current_config.music.library_paths[0]).expanduser()

    # Silently export in the background - don't interrupt user workflow
    try:
        playlist_export.auto_export_playlist(
            playlist_id=playlist_id,
            export_formats=current_config.playlists.export_formats,
            library_root=library_root,
            use_relative_paths=current_config.playlists.use_relative_paths
        )
    except (ValueError, FileNotFoundError, ImportError, OSError) as e:
        # Expected errors - log but don't interrupt workflow
        print(f"Auto-export failed: {e}", file=sys.stderr)
    except Exception as e:
        # Unexpected errors - log for debugging
        print(f"Unexpected error during auto-export: {e}", file=sys.stderr)


def handle_playlist_list_command() -> bool:
    """
    Handle playlist command - interactive dropdown with fuzzy search.
    Uses prompt_toolkit for a smooth autocomplete experience.
    """
    try:
        playlists = playlists.get_playlists_sorted_by_recent()

        if not playlists:
            print("No playlists found. Create one with: playlist new manual <name>")
            return True

        # Check which one is active
        active = playlists.get_active_playlist()
        active_id = active['id'] if active else None

        print(f"\n📋 Select a playlist ({len(playlists)} available)")
        print("💡 Tip: Type to search, use arrow keys to navigate, Enter to select, Ctrl+C to cancel")
        print()

        # Create styled prompt session for playlist selection
        prompt_style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'completion-menu.completion': 'bg:#008888 #ffffff',
            'completion-menu.completion.current': 'bg:#00aaaa #000000',
            'completion-menu.meta.completion': '#888888',
            'completion-menu.meta.completion.current': 'bg:#00aaaa #ffffff',
        })

        playlist_session = PromptSession(
            completer=completers.PlaylistCompleter(),
            style=prompt_style,
            complete_while_typing=True,
        )

        try:
            # Get playlist selection via autocomplete
            selected_name = playlist_session.prompt("🔍 Search: ").strip()

            if not selected_name:
                print("No playlist selected")
                return True

            # Find the selected playlist
            selected_playlist = None
            for pl in playlists:
                if pl['name'] == selected_name:
                    selected_playlist = pl
                    break

            if not selected_playlist:
                print(f"❌ Playlist '{selected_name}' not found")
                return True

            # Activate playlist
            if playlists.set_active_playlist(selected_playlist['id']):
                print(f"\n✅ Activated playlist: {selected_playlist['name']}")

                # Auto-play first track
                playlist_tracks = playlists.get_playlist_tracks(selected_playlist['id'])
                if playlist_tracks:
                    # Convert DB track to library.Track and play
                    first_track = database.db_track_to_library_track(playlist_tracks[0])
                    if play_track(first_track, playlist_position=0):
                        print(f"🎵 Now playing: {library.get_display_name(first_track)}")
                    else:
                        print("❌ Failed to play track")
                else:
                    print(f"⚠️  Playlist is empty")
            else:
                print(f"❌ Failed to activate playlist")

        except KeyboardInterrupt:
            print("\n⚠️  Playlist selection cancelled")

        return True
    except Exception as e:
        print(f"❌ Error browsing playlists: {e}")
        import traceback
        traceback.print_exc()
        return True


def smart_playlist_wizard(name: str) -> bool:
    """Interactive wizard for creating a smart playlist with filters.

    Args:
        name: Name of the playlist to create

    Returns:
        True to continue interactive loop
    """
    print(f"\n🧙 Smart Playlist Wizard: {name}")
    print("=" * 60)
    print("Create filters to automatically match tracks.\n")

    # Create the playlist first
    try:
        playlist_id = playlists.create_playlist(name, 'smart', description=None)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True

    filters_added = []

    # Loop to add filters
    while True:
        print("\n" + "-" * 60)
        print("Add a filter rule:")
        print()

        # Show valid fields
        print("Available fields:")
        print("  Text: title, artist, album, genre, key")
        print("  Numeric: year, bpm")
        print()

        # Get field
        field = input("Field (or 'done' to finish): ").strip().lower()

        if field == 'done':
            if not filters_added:
                print("❌ You must add at least one filter for a smart playlist")
                # Delete the empty playlist
                playlists.delete_playlist(playlist_id)
                return True
            break

        if field not in playlist_filters.VALID_FIELDS:
            print(f"❌ Invalid field. Must be one of: {', '.join(sorted(playlist_filters.VALID_FIELDS))}")
            continue

        # Show valid operators for this field
        if field in playlist_filters.NUMERIC_FIELDS:
            print(f"\nNumeric operators: {', '.join(sorted(playlist_filters.NUMERIC_OPERATORS))}")
            valid_ops = playlist_filters.NUMERIC_OPERATORS
        else:
            print(f"\nText operators: {', '.join(sorted(playlist_filters.TEXT_OPERATORS))}")
            valid_ops = playlist_filters.TEXT_OPERATORS

        # Get operator
        operator = input("Operator: ").strip().lower()

        if operator not in valid_ops:
            print(f"❌ Invalid operator for {field}. Must be one of: {', '.join(sorted(valid_ops))}")
            continue

        # Get value
        value = input("Value: ").strip()

        if not value:
            print("❌ Value cannot be empty")
            continue

        # Determine conjunction for next filter
        conjunction = 'AND'
        if filters_added:
            conj_input = input("Combine with previous filter using AND or OR? [AND]: ").strip().upper()
            if conj_input in ('AND', 'OR'):
                conjunction = conj_input

        # Add filter
        try:
            filter_id = playlist_filters.add_filter(playlist_id, field, operator, value, conjunction)
            filters_added.append({
                'id': filter_id,
                'field': field,
                'operator': operator,
                'value': value,
                'conjunction': conjunction
            })
            print(f"✅ Added filter: {field} {operator} '{value}'")
        except ValueError as e:
            print(f"❌ Error: {e}")
            continue

        # Ask if they want to add another
        more = input("\nAdd another filter? (y/n) [n]: ").strip().lower()
        if more != 'y':
            break

    # Preview matching tracks
    print("\n" + "=" * 60)
    print("📊 Preview: Finding matching tracks...")

    try:
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)
        count = len(matching_tracks)

        print(f"\n✅ Found {count} matching tracks")

        if count > 0:
            print("\nFirst 10 matches:")
            for i, track in enumerate(matching_tracks[:10], 1):
                artist = track.get('artist', 'Unknown')
                title = track.get('title', 'Unknown')
                album = track.get('album', '')
                print(f"  {i}. {artist} - {title}")
                if album:
                    print(f"     Album: {album}")

        # Show filters
        print(f"\n📋 Filter rules for '{name}':")
        for i, f in enumerate(filters_added, 1):
            prefix = f"  {f['conjunction']}" if i > 1 else "  "
            print(f"{prefix} {f['field']} {f['operator']} '{f['value']}'")

        # Confirm
        print()
        confirm = input("Save this smart playlist? (y/n) [y]: ").strip().lower()

        if confirm == 'n':
            playlists.delete_playlist(playlist_id)
            print("❌ Smart playlist cancelled")
            return True

        # Update track count for the smart playlist
        playlists.update_playlist_track_count(playlist_id)

        print(f"\n✅ Created smart playlist: {name}")
        print(f"   {count} tracks match your filters")
        print(f"   Set as active with: playlist active \"{name}\"")

        # Auto-export if enabled
        auto_export_if_enabled(playlist_id)

    except Exception as e:
        print(f"❌ Error evaluating filters: {e}")
        playlists.delete_playlist(playlist_id)
        return True

    return True


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
            playlist_filters.validate_filter(f['field'], f['operator'], f['value'])
        except ValueError as e:
            validation_errors.append(f"Filter {i}: {e}")
    return validation_errors


def ai_smart_playlist_wizard(name: str, description: str) -> bool:
    """AI-powered wizard for creating a smart playlist from natural language.

    Args:
        name: Name of the playlist to create
        description: Natural language description of desired playlist

    Returns:
        True to continue interactive loop
    """
    # Check API key early before doing anything
    if not ai.get_api_key():
        print("❌ No OpenAI API key found. Use 'ai setup <key>' to configure.")
        return True

    print(f"\n🤖 AI Smart Playlist Wizard: {name}")
    print("=" * 60)
    print(f"Description: \"{description}\"")
    print("\n🧠 Parsing with AI...")

    # Parse description with AI
    try:
        filters, metadata = playlist_ai.parse_natural_language_to_filters(description)
        print(f"✅ Parsed in {metadata['response_time_ms']}ms")
        print(f"   Tokens: {metadata['prompt_tokens']} prompt + {metadata['completion_tokens']} completion")

        # Calculate and display estimated cost
        cfg = config.load_config()
        cost = (metadata['prompt_tokens'] * cfg.ai.cost_per_1m_input_tokens / 1_000_000 +
                metadata['completion_tokens'] * cfg.ai.cost_per_1m_output_tokens / 1_000_000)
        print(f"   Estimated cost: ${cost:.6f}")
    except ai.AIError as e:
        print(f"❌ AI Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return True

    # Validate all filters
    print("\n🔍 Validating filters...")
    validation_errors = validate_filters_list(filters)

    if validation_errors:
        print("❌ Validation errors found:")
        for error in validation_errors:
            print(f"   {error}")
        print("\n⚠️  AI generated invalid filters. Please try:")
        print(f"   1. Use simpler description")
        print(f"   2. Use manual filter wizard: playlist new smart \"{name}\"")
        return True

    print(f"✅ All {len(filters)} filters are valid")

    # Show parsed filters
    print("\n📋 Parsed filters:")
    print(playlist_ai.format_filters_for_preview(filters))

    # Ask if user wants to edit
    print("\n" + "=" * 60)
    edit = input("Edit filters before creating playlist? (y/n) [n]: ").strip().lower()

    if edit == 'y':
        try:
            filters = playlist_ai.edit_filters_interactive(filters)
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
            return True

        # Check if filters are empty after editing
        if not filters:
            print("❌ No filters remaining. Cannot create empty smart playlists.")
            return True

        # Re-validate after editing
        validation_errors = validate_filters_list(filters)

        if validation_errors:
            print("❌ Validation errors after editing:")
            for error in validation_errors:
                print(f"   {error}")
            return True

    # Create playlist
    print("\n" + "=" * 60)
    print(f"Creating smart playlist: {name}")

    try:
        playlist_id = playlists.create_playlist(name, 'smart', description=description)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True

    # Add all filters
    try:
        for f in filters:
            playlist_filters.add_filter(
                playlist_id,
                f['field'],
                f['operator'],
                f['value'],
                f.get('conjunction', 'AND')
            )
    except Exception as e:
        print(f"❌ Error adding filters: {e}")
        playlists.delete_playlist(playlist_id)
        return True

    # Preview matching tracks
    print("\n📊 Preview: Finding matching tracks...")

    try:
        matching_tracks = playlist_filters.evaluate_filters(playlist_id)
        count = len(matching_tracks)

        print(f"\n✅ Found {count} matching tracks")

        if count > 0:
            print("\nFirst 10 matches:")
            for i, track in enumerate(matching_tracks[:10], 1):
                artist = track.get('artist', 'Unknown')
                title = track.get('title', 'Unknown')
                album = track.get('album', '')
                print(f"  {i}. {artist} - {title}")
                if album:
                    print(f"     Album: {album}")

        # Show final filters
        print(f"\n📋 Filter rules for '{name}':")
        for i, f in enumerate(filters, 1):
            prefix = f"  {f['conjunction']}" if i > 1 else "  "
            print(f"{prefix} {f['field']} {f['operator']} '{f['value']}'")

        # Confirm
        print()
        confirm = input("Save this smart playlist? (y/n) [y]: ").strip().lower()

        if confirm == 'n':
            playlists.delete_playlist(playlist_id)
            print("❌ Smart playlist cancelled")
            return True

        print(f"\n✅ Created AI smart playlist: {name}")
        print(f"   {count} tracks match your filters")
        print(f"   Description: {description}")
        print(f"   Set as active with: playlist active \"{name}\"")

        # Auto-export if enabled
        auto_export_if_enabled(playlist_id)

    except Exception as e:
        print(f"❌ Error evaluating filters: {e}")
        playlists.delete_playlist(playlist_id)
        return True

    return True


def handle_playlist_new_command(args: List[str]) -> bool:
    """Handle playlist new command - create a new playlists."""
    if len(args) < 2:
        print("Error: Please specify playlist type and name")
        print("Usage: playlist new manual <name>")
        print("       playlist new smart <name>")
        print("       playlist new smart ai <name> \"<description>\"")
        return True

    playlist_type = args[0].lower()
    if playlist_type not in ['manual', 'smart']:
        print(f"Error: Invalid playlist type '{playlist_type}'. Must be 'manual' or 'smart'")
        return True

    # Check for AI smart playlist
    if playlist_type == 'smart' and len(args) >= 2 and args[1].lower() == 'ai':
        # Format: smart ai <name> "<description>"
        # Need to parse name and quoted description
        if len(args) < 3:
            print("Error: Please specify playlist name and description")
            print("Usage: playlist new smart ai <name> \"<description>\"")
            return True

        # Use shlex for proper shell-like parsing
        try:
            # Join everything after 'ai' and parse with shlex
            rest = ' '.join(args[2:])
            parts = shlex.split(rest)

            if len(parts) >= 2:
                name = parts[0]
                description = parts[1]
                return ai_smart_playlist_wizard(name, description)
            else:
                print("Error: Please provide both name and description")
                print("Usage: playlist new smart ai <name> \"<description>\"")
                print("Example: playlist new smart ai NYE2025 \"all dubstep from 2025\"")
                return True

        except ValueError as e:
            print(f"Error parsing command: {e}")
            print("Usage: playlist new smart ai <name> \"<description>\"")
            print("Example: playlist new smart ai NYE2025 \"all dubstep from 2025\"")
            return True

    # Regular smart playlist - launch manual wizard
    if playlist_type == 'smart':
        name = ' '.join(args[1:])
        return smart_playlist_wizard(name)

    # Manual playlist - assign name from remaining args
    name = ' '.join(args[1:])

    try:
        playlist_id = playlists.create_playlist(name, playlist_type, description=None)
        print(f"✅ Created {playlist_type} playlist: {name}")
        print(f"   Playlist ID: {playlist_id}")
        print(f"   Add tracks with: add \"{name}\"")

        # Auto-export if enabled
        auto_export_if_enabled(playlist_id)

        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error creating playlist: {e}")
        return True


def handle_playlist_delete_command(args: List[str]) -> bool:
    """Handle playlist delete command - delete a playlists."""
    if not args:
        print("Error: Please specify playlist name")
        print("Usage: playlist delete <name>")
        return True

    name = ' '.join(args)
    pl = playlists.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    # Confirm deletion
    print(f"⚠️  Delete playlist '{name}'? This cannot be undone.")
    confirm = input("Type 'yes' to confirm: ").strip().lower()

    if confirm != 'yes':
        print("Deletion cancelled")
        return True

    try:
        # Clear position tracking before deleting
        playback.clear_playlist_position(pl['id'])

        if playlists.delete_playlist(pl['id']):
            print(f"✅ Deleted playlist: {name}")
        else:
            print(f"❌ Failed to delete playlist: {name}")
        return True
    except Exception as e:
        print(f"❌ Error deleting playlist: {e}")
        return True


def handle_playlist_rename_command(args: List[str]) -> bool:
    """Handle playlist rename command - rename a playlists."""
    if len(args) < 2:
        print("Error: Please specify old and new names")
        print('Usage: playlist rename "old name" "new name"')
        return True

    # Parse quoted args to handle multi-word playlist names
    parsed_args = parse_quoted_args(args)

    if len(parsed_args) < 2:
        print("Error: Please specify both old and new names")
        print('Usage: playlist rename "old name" "new name"')
        return True

    old_name = parsed_args[0]
    new_name = parsed_args[1]

    pl = playlists.get_playlist_by_name(old_name)
    if not pl:
        print(f"❌ Playlist '{old_name}' not found")
        return True

    try:
        if playlists.rename_playlist(pl['id'], new_name):
            print(f"✅ Renamed playlist: '{old_name}' → '{new_name}'")
        else:
            print(f"❌ Failed to rename playlist")
        return True
    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except Exception as e:
        print(f"❌ Error renaming playlist: {e}")
        return True


def handle_playlist_show_command(args: List[str]) -> bool:
    """Handle playlist show command - show playlist details and tracks."""
    if not args:
        print("Error: Please specify playlist name")
        print("Usage: playlist show <name>")
        return True

    name = ' '.join(args)
    pl = playlists.get_playlist_by_name(name)

    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    try:
        tracks = playlists.get_playlist_tracks(pl['id'])

        print(f"\n📋 Playlist: {pl['name']}")
        print("=" * 60)
        print(f"Type: {pl['type']}")
        if pl['description']:
            print(f"Description: {pl['description']}")
        print(f"Created: {pl['created_at']}")
        print(f"Updated: {pl['updated_at']}")
        print(f"Tracks: {len(tracks)}")
        print()

        if not tracks:
            print("No tracks in this playlist")
            if pl['type'] == 'manual':
                print(f"Add tracks with: add \"{name}\"")
        else:
            print("Tracks:")
            for i, track in enumerate(tracks, 1):
                artist = track.get('artist') or 'Unknown'
                title = track.get('title') or 'Unknown'
                album = track.get('album', '')
                print(f"  {i}. {artist} - {title}")
                if album:
                    print(f"     Album: {album}")

        return True
    except Exception as e:
        print(f"❌ Error showing playlist: {e}")
        return True


def handle_playlist_active_command(args: List[str]) -> bool:
    """Handle playlist active command - set or clear active playlists."""
    if not args:
        # Show current active playlist
        active = playlists.get_active_playlist()
        if active:
            print(f"Active playlist: {active['name']}")
        else:
            print("No active playlist (playing all tracks)")
        return True

    name = ' '.join(args)

    if name.lower() == 'none':
        # Clear active playlist
        # First get the active playlist ID to clear position tracking
        active = playlists.get_active_playlist()
        if active:
            playback.clear_playlist_position(active['id'])

        if playlists.clear_active_playlist():
            print("✅ Cleared active playlist (now playing all tracks)")
        else:
            print("No active playlist was set")
        return True

    # Set active playlist
    pl = playlists.get_playlist_by_name(name)
    if not pl:
        print(f"❌ Playlist '{name}' not found")
        return True

    try:
        if playlists.set_active_playlist(pl['id']):
            print(f"✅ Set active playlist: {name}")
            print(f"   Now playing only tracks from this playlist")

            # Check for saved position and offer to resume
            saved_position = playback.get_playlist_position(pl['id'])
            shuffle_enabled = playback.get_shuffle_mode()

            if saved_position and not shuffle_enabled:
                track_id, position = saved_position
                # Get playlist tracks to find the saved track
                playlist_tracks = playlists.get_playlist_tracks(pl['id'])

                # Find track info
                saved_track = None
                for track in playlist_tracks:
                    if track['id'] == track_id:
                        saved_track = track
                        break

                if saved_track:
                    print(f"\n💾 Last position: Track {position + 1}/{len(playlist_tracks)}")
                    print(f"   {saved_track.get('artist', 'Unknown')} - {saved_track.get('title', 'Unknown')}")

                    response = input("   Resume from this position? [Y/n]: ").strip().lower()
                    if response != 'n':
                        # Load the track and play it
                        if ensure_library_loaded():
                            # Find the Track object from music_tracks
                            music_tracks = get_music_tracks()
                            for track in music_tracks:
                                if track.file_path == saved_track['file_path']:
                                    print("▶️  Resuming playback...")
                                    play_track(track)
                                    break
        else:
            print(f"❌ Failed to set active playlist")
        return True
    except Exception as e:
        print(f"❌ Error setting active playlist: {e}")
        return True


def handle_playlist_import_command(args: List[str]) -> bool:
    """Handle playlist import command - import playlist from file."""
    current_config = get_config()

    if not args:
        print("Error: Please specify playlist file path")
        print("Usage: playlist import <file>")
        print("Supported formats: .m3u, .m3u8, .crate")
        return True

    file_path_str = ' '.join(args)
    file_path = Path(file_path_str).expanduser()

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return True

    # Get library root from config
    # Validate library paths exist
    if not current_config.music.library_paths:
        print("❌ Error: No library paths configured")
        return True
    library_root = Path(current_config.music.library_paths[0]).expanduser()

    # Auto-detect format and import
    try:
        format_type = playlist_import.detect_playlist_format(file_path)
        if not format_type:
            print(f"❌ Unsupported file format: {file_path.suffix}")
            print("Supported formats: .m3u, .m3u8, .crate")
            return True

        print(f"📂 Importing {format_type.upper()} playlist from: {file_path.name}")

        playlist_id, tracks_added, duplicates_skipped, unresolved = playlist_import.import_playlist(
            file_path=file_path,
            playlist_name=None,  # Use filename as default
            library_root=library_root
        )

        # Get the created playlist info
        pl = playlists.get_playlist_by_id(playlist_id)
        if pl:
            print(f"✅ Created playlist: {pl['name']}")
            print(f"   Tracks added: {tracks_added}")
            if duplicates_skipped > 0:
                print(f"   Duplicates skipped: {duplicates_skipped}")

            if unresolved:
                print(f"   ⚠️  Unresolved tracks: {len(unresolved)}")
                if len(unresolved) <= 5:
                    print("\n   Could not find these tracks:")
                    for path in unresolved:
                        # Show just filename for brevity
                        print(f"     • {Path(path).name}")
                else:
                    print(f"   Run 'playlist show {pl['name']}' to see details")

            # Auto-export if enabled
            auto_export_if_enabled(playlist_id)

        return True

    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return True
    except Exception as e:
        print(f"❌ Error importing playlist: {e}")
        return True


def handle_playlist_export_command(args: List[str]) -> bool:
    """Handle playlist export command - export playlist to file."""
    current_config = get_config()

    if not args:
        print("Error: Please specify playlist name")
        print("Usage: playlist export <name> [format]")
        print("Formats: m3u8 (default), crate, all")
        return True

    # Parse arguments with smart format detection
    # Strategy: Try full name first, then try separating format
    format_type = 'm3u8'  # Default format
    playlist_name = ' '.join(args)

    # If more than one arg and last arg looks like a format, try separating
    if len(args) > 1 and args[-1].lower() in ['m3u8', 'm3u', 'crate', 'all']:
        # First check if the full name exists as a playlist
        pl_full = playlists.get_playlist_by_name(playlist_name)
        if not pl_full:
            # Full name doesn't exist, try separating the format
            potential_format = args[-1].lower()
            potential_name = ' '.join(args[:-1])
            pl_separated = playlists.get_playlist_by_name(potential_name)
            if pl_separated:
                # Playlist exists without the last arg, treat it as format
                format_type = potential_format
                playlist_name = potential_name

    # Normalize format
    if format_type == 'm3u':
        format_type = 'm3u8'

    # Get library root from config
    # Validate library paths exist
    if not current_config.music.library_paths:
        print("❌ Error: No library paths configured")
        return True
    library_root = Path(current_config.music.library_paths[0]).expanduser()

    # Check if playlist exists
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        print(f"❌ Playlist '{playlist_name}' not found")
        return True

    try:
        if format_type == 'all':
            # Export to both formats
            formats = ['m3u8', 'crate']
            print(f"📤 Exporting playlist '{playlist_name}' to all formats...")

            for fmt in formats:
                try:
                    output_path, tracks_exported = playlist_export.export_playlist(
                        playlist_name=playlist_name,
                        format_type=fmt,
                        library_root=library_root
                    )
                    print(f"   ✅ {fmt.upper()}: {output_path} ({tracks_exported} tracks)")
                except Exception as e:
                    print(f"   ❌ {fmt.upper()}: {e}")

        else:
            # Export to single format
            print(f"📤 Exporting playlist '{playlist_name}' to {format_type.upper()}...")

            output_path, tracks_exported = playlist_export.export_playlist(
                playlist_name=playlist_name,
                format_type=format_type,
                library_root=library_root
            )

            print(f"✅ Exported {tracks_exported} tracks to: {output_path}")

        return True

    except ValueError as e:
        print(f"❌ Error: {e}")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return True
    except Exception as e:
        print(f"❌ Error exporting playlist: {e}")
        return True
