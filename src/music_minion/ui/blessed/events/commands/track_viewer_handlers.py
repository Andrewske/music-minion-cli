"""Track viewer command handlers."""

from dataclasses import replace
from music_minion.context import AppContext
from music_minion.ui.blessed.state import (
    UIState,
    add_history_line,
    set_feedback,
    show_track_viewer,
    hide_track_viewer,
)


def handle_show_track_viewer(
    ctx: AppContext,
    ui_state: UIState,
    playlist_name: str,
    playlist_type: str = '',
    tracks: list | None = None
) -> tuple[AppContext, UIState]:
    """
    Handle showing track viewer for a playlist or history.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_name: Name of playlist to view (or display name for history)
        playlist_type: Type of playlist ('history' for special handling, '' for regular)
        tracks: Optional pre-fetched tracks (for history or other special cases)

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    # Handle history or other special cases with pre-fetched tracks
    if playlist_type == 'history' and tracks is not None:
        # Use virtual playlist ID -1 for history (not a real playlist)
        ui_state = show_track_viewer(
            ui_state,
            playlist_id=-1,
            playlist_name=playlist_name,
            playlist_type='history',
            tracks=tracks
        )
        return ctx, ui_state

    # Regular playlist handling
    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        return ctx, ui_state

    # Get playlist tracks
    tracks = playlists.get_playlist_tracks(pl['id'])

    # Show track viewer
    ui_state = show_track_viewer(
        ui_state,
        playlist_id=pl['id'],
        playlist_name=pl['name'],
        playlist_type=pl['type'],
        tracks=tracks
    )

    return ctx, ui_state


def handle_play_track_from_viewer(ctx: AppContext, ui_state: UIState, playlist_id: int, track_index: int) -> tuple[AppContext, UIState]:
    """
    Handle playing a track from the track viewer.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_id: ID of playlist containing track
        track_index: Index of track in viewer

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core import database
    from music_minion.commands.playback import play_track

    # Validate inputs
    if playlist_id < 0:
        ui_state = add_history_line(ui_state, f"❌ Invalid playlist ID: {playlist_id}", 'red')
        return ctx, ui_state

    if track_index < 0:
        ui_state = add_history_line(ui_state, f"❌ Invalid track index: {track_index}", 'red')
        return ctx, ui_state

    # Use tracks from UI state (already loaded)
    tracks = ui_state.track_viewer_tracks

    if track_index >= len(tracks):
        ui_state = add_history_line(ui_state, f"❌ Track index out of range: {track_index}", 'red')
        return ctx, ui_state

    # Get the selected track
    selected_track = tracks[track_index]

    # Convert to library track format
    library_track = database.db_track_to_library_track(selected_track)

    # Play the track with position for sequential mode
    ctx, _ = play_track(ctx, library_track, playlist_position=track_index)

    # Add feedback
    artist = library_track.artist or 'Unknown'
    title = library_track.title or 'Unknown'
    ui_state = add_history_line(ui_state, f"▶️  Now playing: {artist} - {title}", 'white')
    ui_state = set_feedback(ui_state, f"✓ Playing from viewer", "✓")

    # Keep viewer open
    return ctx, ui_state


def handle_remove_track_from_playlist(ctx: AppContext, ui_state: UIState, track_id: int, playlist_name: str) -> tuple[AppContext, UIState]:
    """
    Handle removing a track from a manual playlist.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to remove
        playlist_name: Name of playlist

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists

    # Validate inputs
    if track_id < 0:
        ui_state = add_history_line(ui_state, f"❌ Invalid track ID: {track_id}", 'red')
        ui_state = hide_track_viewer(ui_state)
        return ctx, ui_state

    if not playlist_name or not playlist_name.strip():
        ui_state = add_history_line(ui_state, "❌ Playlist name cannot be empty", 'red')
        ui_state = hide_track_viewer(ui_state)
        return ctx, ui_state

    # Get playlist by name
    pl = playlists.get_playlist_by_name(playlist_name)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist '{playlist_name}' not found", 'red')
        ui_state = hide_track_viewer(ui_state)
        return ctx, ui_state

    # Remove track from playlist
    try:
        playlists.remove_track_from_playlist(pl['id'], track_id)
        ui_state = add_history_line(ui_state, f"✅ Removed track from playlist", 'green')
        ui_state = set_feedback(ui_state, f"✓ Removed from {playlist_name}", "✓")

        # Refresh track list in viewer
        tracks = playlists.get_playlist_tracks(pl['id'])

        if not tracks:
            # No tracks left, close viewer
            ui_state = hide_track_viewer(ui_state)
            ui_state = add_history_line(ui_state, "Playlist is now empty", 'white')
        else:
            # Update viewer with new track list
            # Adjust selection if needed
            new_selected = min(ui_state.track_viewer_selected, len(tracks) - 1)
            ui_state = show_track_viewer(
                ui_state,
                playlist_id=pl['id'],
                playlist_name=pl['name'],
                playlist_type=pl['type'],
                tracks=tracks
            )
            ui_state = replace(ui_state, track_viewer_selected=new_selected)

    except (ValueError, KeyError, TypeError) as e:
        # Database or data structure errors
        ui_state = add_history_line(ui_state, f"❌ Error removing track: {e}", 'red')
    except OSError as e:
        # File system errors
        ui_state = add_history_line(ui_state, f"❌ Database error: {e}", 'red')

    return ctx, ui_state


def handle_track_viewer_play(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle playing a track from track viewer by track ID.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to play

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core import database
    from music_minion.commands.playback import play_track

    # Get track from database
    track = database.get_track_by_id(track_id)
    if not track:
        ui_state = add_history_line(ui_state, f"❌ Track not found: {track_id}", 'red')
        return ctx, ui_state

    # Convert to library track format
    library_track = database.db_track_to_library_track(track)

    # Play the track
    ctx, _ = play_track(ctx, library_track)

    # Add feedback
    artist = library_track.artist or 'Unknown'
    title = library_track.title or 'Unknown'
    ui_state = add_history_line(ui_state, f"▶️  Now playing: {artist} - {title}", 'white')
    ui_state = set_feedback(ui_state, "✓ Playing track", "✓")

    # Keep viewer open
    return ctx, ui_state


def handle_track_viewer_edit(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle editing track metadata from track viewer.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to edit

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core import database
    from music_minion.ui.blessed.state import show_metadata_editor

    # Get track from database with all metadata
    track = database.get_track_by_id(track_id)
    if not track:
        ui_state = add_history_line(ui_state, f"❌ Track not found: {track_id}", 'red')
        return ctx, ui_state

    # Get tags and notes
    tags = database.get_track_tags(track_id)
    notes = database.get_track_notes(track_id)

    # Build track data for editor
    track_data = {
        'id': track_id,
        'title': track.get('title', ''),
        'artist': track.get('artist', ''),
        'album': track.get('album', ''),
        'genre': track.get('genre', ''),
        'year': track.get('year'),
        'bpm': track.get('bpm'),
        'key_signature': track.get('key_signature', ''),
        'tags': [tag['tag_name'] for tag in tags],
        'notes': [note['note_text'] for note in notes],
    }

    # Open metadata editor
    ui_state = show_metadata_editor(ui_state, track_data)

    return ctx, ui_state


def handle_track_viewer_add_to_playlist(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle adding track to another playlist from track viewer.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to add

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.ui.blessed.components.palette import load_playlist_items
    from music_minion.ui.blessed.state import show_playlist_palette

    # Load playlists and show palette for selection
    items = load_playlist_items(ui_state.active_library)

    if not items:
        ui_state = add_history_line(ui_state, "❌ No playlists available", 'red')
        return ctx, ui_state

    # Show playlist palette - selection will be handled by InternalCommand
    ui_state = show_playlist_palette(ui_state, items)

    # Store track_id in context for later use (when playlist is selected)
    # For now, we'll use feedback to indicate what we're doing
    ui_state = set_feedback(ui_state, "Select playlist to add track to", "→")

    return ctx, ui_state


def handle_track_viewer_remove(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle removing track from manual playlist (wrapper for confirmation dialog result).

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to remove

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    # Get playlist name from viewer state
    playlist_name = ui_state.track_viewer_playlist_name

    # Delegate to existing remove handler
    return handle_remove_track_from_playlist(ctx, ui_state, track_id, playlist_name)


def handle_track_viewer_edit_filters(ctx: AppContext, ui_state: UIState, playlist_id: int) -> tuple[AppContext, UIState]:
    """
    Handle editing filters for a smart playlist.

    Args:
        ctx: Application context
        ui_state: Current UI state
        playlist_id: ID of smart playlist to edit

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.domain import playlists
    from music_minion.ui.blessed.state import start_wizard

    # Get playlist
    pl = playlists.get_playlist_by_id(playlist_id)
    if not pl:
        ui_state = add_history_line(ui_state, f"❌ Playlist not found", 'red')
        return ctx, ui_state

    if pl['type'] != 'smart':
        ui_state = add_history_line(ui_state, f"❌ Cannot edit filters on manual playlist", 'red')
        return ctx, ui_state

    # Get existing filters
    filters = playlists.get_playlist_filters(playlist_id)

    # Start wizard in edit mode with existing filters
    wizard_data = {
        'name': pl['name'],
        'playlist_id': playlist_id,
        'filters': filters,
        'edit_mode': True
    }

    ui_state = start_wizard(ui_state, 'smart_playlist', wizard_data)

    return ctx, ui_state


def handle_track_viewer_like(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle liking a track from track viewer.

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to like

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from datetime import datetime
    from music_minion.core import database
    from music_minion.domain import library

    # Get track from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        ui_state = add_history_line(ui_state, f"❌ Track not found: {track_id}", 'red')
        return ctx, ui_state

    # Convert to library track for display name
    library_track = database.db_track_to_library_track(db_track)

    # Add like rating
    database.add_rating(track_id, 'like', 'User liked song', source='user')

    # Show temporal context
    now = datetime.now()
    time_context = f"{now.strftime('%A')} at {now.hour:02d}:{now.minute:02d}"

    # Add feedback
    ui_state = add_history_line(ui_state, f"👍 Liked: {library.get_display_name(library_track)}", 'white')
    ui_state = add_history_line(ui_state, f"   Liked on {time_context}", 'white')
    ui_state = set_feedback(ui_state, "✓ Liked track", "✓")

    # Sync to SoundCloud if track has soundcloud_id
    soundcloud_id = db_track.get('soundcloud_id')
    if soundcloud_id:
        # Check if already liked on SoundCloud
        if not database.has_soundcloud_like(track_id):
            # Sync like to SoundCloud
            from music_minion.domain.library import providers

            try:
                # Get SoundCloud provider
                provider = providers.get_provider('soundcloud')
                from music_minion.domain.library.provider import ProviderConfig
                config = ProviderConfig(name='soundcloud', enabled=True)
                state = provider.init_provider(config)

                if state.authenticated:
                    # Call API to like track
                    new_state, success, error_msg = provider.like_track(state, soundcloud_id)

                    if success:
                        # Add soundcloud marker to database
                        database.add_rating(track_id, 'like', 'Synced to SoundCloud', source='soundcloud')
                        ui_state = add_history_line(ui_state, "   ✓ Synced like to SoundCloud", 'white')
                    else:
                        ui_state = add_history_line(ui_state, f"   ⚠ Failed to sync to SoundCloud: {error_msg}", 'yellow')
                else:
                    # Not authenticated - skip silently
                    pass
            except Exception as e:
                ui_state = add_history_line(ui_state, f"   ⚠ Error syncing to SoundCloud: {e}", 'yellow')

    # Keep viewer open
    return ctx, ui_state


def handle_track_viewer_unlike(ctx: AppContext, ui_state: UIState, track_id: int) -> tuple[AppContext, UIState]:
    """
    Handle unliking a track from track viewer.

    Only removes the SoundCloud like marker and syncs to SoundCloud.
    Does not remove local user likes (those are temporal data).

    Args:
        ctx: Application context
        ui_state: Current UI state
        track_id: ID of track to unlike

    Returns:
        Tuple of (updated AppContext, updated UIState)
    """
    from music_minion.core import database
    from music_minion.domain import library

    # Get track from database
    db_track = database.get_track_by_id(track_id)
    if not db_track:
        ui_state = add_history_line(ui_state, f"❌ Track not found: {track_id}", 'red')
        return ctx, ui_state

    # Convert to library track for display name
    library_track = database.db_track_to_library_track(db_track)

    soundcloud_id = db_track.get('soundcloud_id')

    # Check if track has SoundCloud like marker
    if not database.has_soundcloud_like(track_id):
        ui_state = add_history_line(ui_state, f"⚠ {library.get_display_name(library_track)}", 'yellow')
        ui_state = add_history_line(ui_state, "   Track is not liked on SoundCloud", 'yellow')
        return ctx, ui_state

    # Track has SoundCloud like, proceed to unlike
    if not soundcloud_id:
        ui_state = add_history_line(ui_state, f"⚠ {library.get_display_name(library_track)}", 'yellow')
        ui_state = add_history_line(ui_state, "   Track has like marker but no SoundCloud ID", 'yellow')
        return ctx, ui_state

    # Remove SoundCloud like via API
    from music_minion.domain.library import providers

    try:
        # Get SoundCloud provider
        provider = providers.get_provider('soundcloud')
        from music_minion.domain.library.provider import ProviderConfig
        config = ProviderConfig(name='soundcloud', enabled=True)
        state = provider.init_provider(config)

        if not state.authenticated:
            ui_state = add_history_line(ui_state, "⚠ Not authenticated with SoundCloud", 'yellow')
            ui_state = add_history_line(ui_state, "   Run: library auth soundcloud", 'yellow')
            return ctx, ui_state

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

            ui_state = add_history_line(ui_state, f"💔 Unliked on SoundCloud: {library.get_display_name(library_track)}", 'white')
            ui_state = add_history_line(ui_state, "   ✓ Removed like from SoundCloud", 'white')
            ui_state = set_feedback(ui_state, "✓ Unliked track", "✓")
        else:
            ui_state = add_history_line(ui_state, f"⚠ Failed to unlike on SoundCloud: {error_msg}", 'yellow')

    except Exception as e:
        ui_state = add_history_line(ui_state, f"⚠ Error unliking on SoundCloud: {e}", 'yellow')

    # Keep viewer open
    return ctx, ui_state
