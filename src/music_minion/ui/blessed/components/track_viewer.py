"""Track viewer rendering for playlist tracks."""

from blessed import Terminal

from ..helpers import write_at
from ..state import UIState

# Layout constants
TRACK_VIEWER_HEADER_LINES = 2  # Title + metadata line
TRACK_VIEWER_FOOTER_LINES = 1


def render_track_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render track viewer with scrolling support (2-mode: list/detail).

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for viewer
    """
    if not state.track_viewer_visible or height <= 0:
        return

    all_tracks = state.track_viewer_tracks
    filtered_tracks = state.track_viewer_filtered_tracks
    filter_query = state.track_viewer_filter_query
    selected_index = state.track_viewer_selected
    scroll_offset = state.track_viewer_scroll
    playlist_name = state.track_viewer_playlist_name
    playlist_type = state.track_viewer_playlist_type
    viewer_mode = state.track_viewer_mode

    # Reserve lines for header and footer
    content_height = height - TRACK_VIEWER_HEADER_LINES - TRACK_VIEWER_FOOTER_LINES

    # Calculate max width for track text based on terminal width
    # Reserve space for: 2 spaces indent + 3 digits position + ". " separator + 2 for safety
    max_track_width = max(40, term.width - 9)

    line_num = 0

    # Header - different based on mode
    if line_num < height:
        if viewer_mode == 'detail':
            header_text = f"   🎵 Track Details"
        else:
            header_text = f"   📋 Playlist: {playlist_name}"
        write_at(term, 0, y + line_num, term.bold_cyan(header_text))
        line_num += 1

    # Metadata line - type, track count, and filter indicator (only in list mode)
    if viewer_mode == 'list' and line_num < height:
        # Select icon based on playlist type
        if playlist_type == 'history':
            type_icon = "🕐"
        elif playlist_type == 'smart':
            type_icon = "🧠"
        else:
            type_icon = "📝"

        # Add read-only indicator for history
        type_display = f"{playlist_type.capitalize()} (Read-Only)" if playlist_type == 'history' else playlist_type.capitalize()

        if filter_query:
            # Show filtered count and total
            metadata_text = f"   {type_icon} {type_display} • {len(filtered_tracks)}/{len(all_tracks)} tracks (filter: {filter_query})"
        else:
            # Show total count
            metadata_text = f"   {type_icon} {type_display} • {len(all_tracks)} tracks"
        write_at(term, 0, y + line_num, term.white(metadata_text))
        line_num += 1

    # Render based on mode
    if viewer_mode == 'detail' and filtered_tracks and selected_index < len(filtered_tracks):
        # Detail mode: show track details and action menu
        selected_track = filtered_tracks[selected_index]
        line_num = _render_track_detail_and_actions(
            term, state, selected_track, playlist_type,
            y, line_num, height, TRACK_VIEWER_FOOTER_LINES, content_height
        )
    elif viewer_mode == 'list':
        # List mode: show track list (filtered)
        if not filtered_tracks:
            if line_num < height:
                if filter_query:
                    empty_msg = f"  No tracks match filter: '{filter_query}'"
                else:
                    empty_msg = "  No tracks in this playlist"
                write_at(term, 0, y + line_num, term.white(empty_msg))
                line_num += 1
        else:
            # Batch query for liked tracks (performance optimization)
            liked_track_ids = set()
            try:
                from music_minion.core import database
                track_ids = [t.get('id') for t in filtered_tracks if t.get('id')]
                if track_ids:
                    with database.get_db_connection() as conn:
                        placeholders = ','.join('?' * len(track_ids))
                        cursor = conn.execute(f"""
                            SELECT DISTINCT track_id
                            FROM ratings
                            WHERE track_id IN ({placeholders})
                            AND rating_type = 'like'
                        """, track_ids)
                        liked_track_ids = {row['track_id'] for row in cursor.fetchall()}
            except Exception:
                pass  # Ignore errors, don't break UI

            # Render filtered tracks with scroll offset
            items_rendered = 0
            for track_index, track in enumerate(filtered_tracks):
                # Skip tracks before scroll offset
                if track_index < scroll_offset:
                    continue

                # Stop if we've filled the content area
                if items_rendered >= content_height:
                    break

                if line_num >= height - TRACK_VIEWER_FOOTER_LINES:
                    break

                # Format track info
                position = track_index + 1
                artist = track.get('artist', 'Unknown')
                title = track.get('title', 'Unknown')
                track_id = track.get('id')

                is_selected = track_index == selected_index
                is_liked = track_id in liked_track_ids

                # Track line: position, artist - title [heart]
                heart = " ♥" if is_liked else ""
                track_text = f"{position:3d}. {artist} - {title}{heart}"

                if is_selected:
                    # Selected item: highlighted background
                    item_line = term.black_on_cyan(f"  {track_text[:max_track_width]}")
                else:
                    # Normal item
                    item_line = term.white(f"  {track_text[:max_track_width]}")

                write_at(term, 0, y + line_num, item_line)
                line_num += 1
                items_rendered += 1

    # Clear remaining lines
    while line_num < height - TRACK_VIEWER_FOOTER_LINES:
        write_at(term, 0, y + line_num, "")
        line_num += 1

    # Footer help text - different based on mode
    if line_num < height:
        if viewer_mode == 'detail':
            # Detail mode: show action navigation help
            footer = "   ↑↓ navigate  Enter select  p/l/u/e/a shortcuts  Esc back"
        else:
            # List mode: show track navigation help
            total_tracks = len(filtered_tracks)  # Show filtered count for navigation
            if playlist_type == 'history':
                # History: read-only (no delete, no filters)
                if total_tracks > content_height:
                    current_position = min(selected_index + 1, total_tracks)
                    footer = f"   [{current_position}/{total_tracks}] ↑↓/j/k nav  Enter  p/l/u/e/a  q close"
                else:
                    footer = "   ↑↓/j/k navigate  Enter details  p/l/u/e/a (play/like/unlike/edit/add)  q close"
            elif playlist_type == 'manual':
                # Manual playlist: can remove tracks and enter builder mode
                if total_tracks > content_height:
                    current_position = min(selected_index + 1, total_tracks)
                    footer = f"   [{current_position}/{total_tracks}] ↑↓/j/k nav  Enter  p/l/u/d/e/a/b  q close"
                else:
                    footer = "   ↑↓/j/k navigate  Enter details  p/l/u/d/e/a/b (play/like/unlike/del/edit/add/build)  q close"
            else:
                # Smart playlist: read-only (no delete, but can edit filters)
                if total_tracks > content_height:
                    current_position = min(selected_index + 1, total_tracks)
                    footer = f"   [{current_position}/{total_tracks}] ↑↓/j/k nav  Enter  p/l/u/e/a/f  q close"
                else:
                    footer = "   ↑↓/j/k navigate  Enter details  p/l/u/e/a/f (play/like/unlike/edit/add/filters)  q close"

        write_at(term, 0, y + line_num, term.white(footer))
        line_num += 1


def _render_track_detail_and_actions(
    term: Terminal,
    state: UIState,
    track: dict,
    playlist_type: str,
    y: int,
    line_num: int,
    height: int,
    footer_lines: int,
    content_height: int
) -> int:
    """
    Render track details and action menu.

    Args:
        term: Terminal instance
        state: UI state
        track: Track dictionary
        playlist_type: Type of playlist ('manual' or 'smart')
        y: Starting Y position
        line_num: Current line number
        height: Total height
        footer_lines: Number of footer lines
        content_height: Available content height

    Returns:
        Updated line_num
    """
    # Check if track is liked
    track_id = track.get('id')
    is_liked = False
    if track_id:
        from music_minion.core import database
        try:
            ratings = database.get_track_ratings(track_id)
            # Check if there's any 'like' rating with source='user' or 'soundcloud'
            is_liked = any(r.get('rating_type') == 'like' for r in ratings)
        except Exception:
            pass  # Ignore errors, don't break UI

    # Track metadata fields to display
    fields = [
        ('Title', track.get('title', 'Unknown')),
        ('Artist', track.get('artist', 'Unknown')),
        ('Album', track.get('album', '')),
        ('Genre', track.get('genre', '')),
        ('Year', str(track.get('year', '')) if track.get('year') else ''),
        ('BPM', str(track.get('bpm', '')) if track.get('bpm') else ''),
        ('Key', track.get('key_signature', '')),
    ]

    # Add like status
    if is_liked:
        fields.append(('Liked', '♥ Yes'))

    # Add tags and notes if present (database returns comma-separated strings)
    tags = track.get('tags', '')  # String, not list
    if tags:
        fields.append(('Tags', tags))

    notes = track.get('notes', '')  # String, not list
    if notes:
        fields.append(('Notes', notes))

    # Render metadata fields
    for field_name, field_value in fields:
        if line_num >= height - footer_lines - 5:  # Reserve space for action menu
            break

        if field_value:  # Only show non-empty fields
            # Format: "  Field: Value"
            field_line = term.cyan(f"  {field_name}: ") + term.white(str(field_value))
            write_at(term, 0, y + line_num, field_line)
            line_num += 1

    # Add spacing before action menu
    if line_num < height - footer_lines:
        write_at(term, 0, y + line_num, "")
        line_num += 1

    # Render action menu (context-aware based on playlist type)
    if line_num < height - footer_lines:
        action_header = term.bold_cyan("  Actions:")
        write_at(term, 0, y + line_num, action_header)
        line_num += 1

    # Define actions based on playlist type
    if playlist_type == 'manual':
        actions = [
            ('p', 'Play Track'),
            ('l', 'Like Track'),
            ('u', 'Unlike Track'),
            ('d', 'Remove from Playlist'),
            ('e', 'Edit Metadata'),
            ('a', 'Add to Another Playlist'),
            ('', 'Cancel')
        ]
    else:  # smart playlist or history - read-only (no delete)
        actions = [
            ('p', 'Play Track'),
            ('l', 'Like Track'),
            ('u', 'Unlike Track'),
            ('e', 'Edit Metadata'),
            ('a', 'Add to Another Playlist'),
            ('', 'Cancel')
        ]

    # Render each action with selection highlighting
    for action_index, (shortcut, action_text) in enumerate(actions):
        if line_num >= height - footer_lines:
            break

        is_selected = action_index == state.track_viewer_action_selected

        # Format action line
        if shortcut:
            action_line = f"    [{shortcut}] {action_text}"
        else:
            action_line = f"        {action_text}"

        if is_selected:
            # Selected action: highlighted background
            write_at(term, 0, y + line_num, term.black_on_cyan(action_line))
        else:
            # Normal action
            write_at(term, 0, y + line_num, term.white(action_line))

        line_num += 1

    return line_num
