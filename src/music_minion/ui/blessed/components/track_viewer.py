"""Track viewer rendering for playlist tracks."""

import sys
from blessed import Terminal
from ..state import UIState


def render_track_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render track viewer with scrolling support.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for viewer
    """
    if not state.track_viewer_visible or height <= 0:
        return

    tracks = state.track_viewer_tracks
    selected_index = state.track_viewer_selected
    scroll_offset = state.track_viewer_scroll
    playlist_name = state.track_viewer_playlist_name
    playlist_type = state.track_viewer_playlist_type

    # Reserve lines for header and footer
    header_lines = 2  # Title + metadata line
    footer_lines = 1
    content_height = height - header_lines - footer_lines

    line_num = 0

    # Header - playlist title
    if line_num < height:
        header_text = f"   📋 Playlist: {playlist_name}"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.bold_cyan(header_text))
        line_num += 1

    # Metadata line - type and track count
    if line_num < height:
        type_icon = "🧠" if playlist_type == 'smart' else "📝"
        metadata_text = f"   {type_icon} {playlist_type.capitalize()} • {len(tracks)} tracks"
        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(metadata_text))
        line_num += 1

    # Render tracks
    if not tracks:
        if line_num < height:
            empty_msg = "  No tracks in this playlist"
            sys.stdout.write(term.move_xy(0, y + line_num) + term.white(empty_msg))
            line_num += 1
    else:
        # Render tracks with scroll offset
        items_rendered = 0
        for track_index, track in enumerate(tracks):
            # Skip tracks before scroll offset
            if track_index < scroll_offset:
                continue

            # Stop if we've filled the content area
            if items_rendered >= content_height:
                break

            if line_num >= height - footer_lines:
                break

            # Format track info
            position = track_index + 1
            artist = track.get('artist', 'Unknown')
            title = track.get('title', 'Unknown')
            album = track.get('album', '')

            is_selected = track_index == selected_index

            # Track line: position, artist - title
            track_text = f"{position:3d}. {artist} - {title}"

            if is_selected:
                # Selected item: highlighted background
                item_line = term.black_on_cyan(f"  {track_text[:76]}")
            else:
                # Normal item
                item_line = term.white(f"  {track_text[:76]}")

            sys.stdout.write(term.move_xy(0, y + line_num) + item_line)
            line_num += 1
            items_rendered += 1

    # Clear remaining lines
    while line_num < height - footer_lines:
        sys.stdout.write(term.move_xy(0, y + line_num) + term.clear_eol)
        line_num += 1

    # Footer help text
    if line_num < height:
        total_tracks = len(tracks)
        if playlist_type == 'manual':
            # Manual playlist: can remove tracks
            if total_tracks > content_height:
                current_position = min(selected_index + 1, total_tracks)
                footer = f"   [{current_position}/{total_tracks}] ↑↓ navigate  Enter play  Del remove  Esc close"
            else:
                footer = "   ↑↓ navigate  Enter play  Del remove  Esc close"
        else:
            # Smart playlist: read-only
            if total_tracks > content_height:
                current_position = min(selected_index + 1, total_tracks)
                footer = f"   [{current_position}/{total_tracks}] ↑↓ navigate  Enter play  Esc close"
            else:
                footer = "   ↑↓ navigate  Enter play  Esc close"

        sys.stdout.write(term.move_xy(0, y + line_num) + term.white(footer))
        line_num += 1
