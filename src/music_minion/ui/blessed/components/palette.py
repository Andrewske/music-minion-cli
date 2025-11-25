"""Command palette rendering functions."""

from blessed import Terminal

from ..helpers import write_at
from ..state import UIState


def load_playlist_items(active_library: str = "all") -> list[tuple[str, str, str, str]]:
    """
    Load playlists from database and convert to palette items format.

    Args:
        active_library: Active library filter ('local', 'soundcloud', 'spotify', 'youtube', 'all')
                        Defaults to 'all' to show all playlists.

    Returns:
        List of palette items: (category, name, icon, description)
    """
    # Import here to avoid circular dependencies
    from ....domain.playlists import crud as playlists

    all_playlists = playlists.get_playlists_sorted_by_recent(library=active_library)
    active = playlists.get_active_playlist()
    active_id = active["id"] if active else None

    items = []
    for pl in all_playlists:
        # Determine category and icon
        category = pl["type"].capitalize()
        icon = "★" if pl["id"] == active_id else "◦"

        # Build description with track count and type
        track_count = pl.get("track_count", 0)
        desc = f"{track_count} tracks"
        if pl["type"] == "smart":
            desc = f"Smart • {desc}"

        # Add active indicator to description if active
        if pl["id"] == active_id:
            desc = f"ACTIVE • {desc}"

        items.append((category, pl["name"], icon, desc))

    return items


def filter_playlist_items(
    query: str, items: list[tuple[str, str, str, str]]
) -> list[tuple[str, str, str, str]]:
    """
    Filter playlist items by name (case-insensitive substring match).

    Args:
        query: Search query string
        items: List of playlist items to filter

    Returns:
        Filtered list of items matching query
    """
    if not query:
        return items

    query_lower = query.lower()
    filtered = []
    for item in items:
        cat, name, icon, desc = item
        # Match against playlist name (case-insensitive)
        if query_lower in name.lower():
            filtered.append(item)

    return filtered


def load_rankings_items(tracks: list[dict]) -> list[tuple[str, str, str, str, int]]:
    """
    Convert ranked tracks to palette items format.

    Args:
        tracks: List of track dicts with rating info from get_leaderboard()

    Returns:
        List of palette items: (rank, artist_title, rating_icon, rating_info, track_id)
    """
    items = []
    for i, track in enumerate(tracks, 1):
        # Format rank with padding
        rank = f"#{i:<3}"

        # Format artist - title
        artist = track.get("artist", "Unknown")
        title = track.get("title", "Unknown")
        artist_title = f"{artist} - {title}"

        # Rating icon based on rating value
        rating = track.get("rating", 1500)
        if rating >= 1700:
            icon = "🔥"  # Fire for top rated
        elif rating >= 1600:
            icon = "⭐"  # Star for high rated
        elif rating >= 1500:
            icon = "✓"  # Check for above average
        else:
            icon = "◦"  # Dot for lower rated

        # Rating info with comparison count
        comparisons = track.get("comparison_count", 0)
        rating_info = f"Rating: {rating:.0f} ({comparisons} comparisons)"

        # Track ID for playing
        track_id = track.get("id", 0)

        items.append((rank, artist_title, icon, rating_info, track_id))

    return items


def filter_rankings_items(
    query: str, items: list[tuple[str, str, str, str, int]]
) -> list[tuple[str, str, str, str, int]]:
    """
    Filter ranking items by artist/title (case-insensitive substring match).

    Args:
        query: Search query string
        items: List of ranking items to filter

    Returns:
        Filtered list of items matching query
    """
    if not query:
        return items

    query_lower = query.lower()
    filtered = []
    for item in items:
        rank, artist_title, icon, rating_info, track_id = item
        # Match against artist-title (case-insensitive)
        if query_lower in artist_title.lower():
            filtered.append(item)

    return filtered


def render_palette(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render command palette with scrolling support.

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for palette
    """
    if not state.palette_visible or height <= 0:
        return

    filtered_commands = state.palette_items
    selected_index = state.palette_selected
    scroll_offset = state.palette_scroll

    # Reserve lines for header and footer
    header_lines = 1
    footer_lines = 1
    content_height = height - header_lines - footer_lines

    line_num = 0

    # Header - different based on palette mode
    if line_num < height:
        if state.palette_mode == "playlist":
            header_text = "   📋 Select Playlist"
        elif state.palette_mode == "device":
            header_text = "   🎵 Select Spotify Device"
        elif state.palette_mode == "rankings":
            # Use stored title from palette_query or default
            title = state.palette_query if state.palette_query else "Top Rated Tracks"
            header_text = f"   🏆 {title}"
        elif state.palette_mode == "search":
            # Show current mode in header
            if state.search_mode == "detail":
                header_text = "   🔍 Track Details"
            else:
                header_text = "   🔍 Track Search"
        else:
            header_text = "   Command Palette"
        write_at(term, 0, y + line_num, term.bold_cyan(header_text))
        line_num += 1

    # Render items (different handling for search mode)
    if state.palette_mode == "search":
        # Different rendering based on search mode (search/detail/action)
        if state.search_mode == "search":
            # Render track search results
            filtered_tracks = state.search_filtered_tracks
            if not filtered_tracks:
                if line_num < height:
                    empty_msg = "  No matching tracks found"
                    write_at(term, 0, y + line_num, term.white(empty_msg))
                    line_num += 1
            else:
                # Render tracks with scroll offset
                items_rendered = 0
                for track_index, track in enumerate(filtered_tracks):
                    # Skip items before scroll offset
                    if track_index < state.search_scroll:
                        continue

                    # Stop if we've filled the content area
                    if items_rendered >= content_height:
                        break

                    if line_num >= height - footer_lines:
                        break

                    # Format track display: "Artist - Title (Album)"
                    is_selected = track_index == state.search_selected
                    artist = track.get("artist", "Unknown")
                    title = track.get("title", "Unknown")
                    album = track.get("album", "")

                    if album:
                        track_text = f"{artist} - {title} ({album})"
                    else:
                        track_text = f"{artist} - {title}"

                    # Truncate if too long
                    max_width = term.width - 6
                    if len(track_text) > max_width:
                        track_text = track_text[: max_width - 3] + "..."

                    if is_selected:
                        # Selected track: highlighted background
                        item_line = term.black_on_cyan(f"  ♪ {track_text}")
                    else:
                        # Normal track
                        item_line = term.bold("  ♪ ") + term.white(track_text)

                    write_at(term, 0, y + line_num, item_line)
                    line_num += 1
                    items_rendered += 1

        elif state.search_mode == "detail":
            # Render combined detail + actions view
            if state.search_filtered_tracks and state.search_selected < len(
                state.search_filtered_tracks
            ):
                selected_track = state.search_filtered_tracks[state.search_selected]
                line_num = _render_track_detail(
                    term,
                    state,
                    selected_track,
                    y,
                    line_num,
                    height,
                    footer_lines,
                    content_height,
                )
    else:
        # Render command/playlist/device/rankings items (existing logic)
        if not filtered_commands:
            if line_num < height:
                empty_msg = (
                    "  No devices found"
                    if state.palette_mode == "device"
                    else "  No playlists found"
                    if state.palette_mode == "playlist"
                    else "  No ranked tracks found"
                    if state.palette_mode == "rankings"
                    else "  No matching commands"
                )
                write_at(term, 0, y + line_num, term.white(empty_msg))
                line_num += 1
        else:
            # Render items with scroll offset
            items_rendered = 0
            for item_index, item in enumerate(filtered_commands):
                # Skip items before scroll offset
                if item_index < scroll_offset:
                    continue

                # Stop if we've filled the content area
                if items_rendered >= content_height:
                    break

                if line_num >= height - footer_lines:
                    break

                # Handle different item formats based on palette mode
                is_selected = item_index == selected_index

                if state.palette_mode == "device":
                    # Device items: (display_name, description, command, device_id)
                    display_name, description, command, device_id = item

                    if is_selected:
                        # Selected device: highlighted background
                        item_line = term.black_on_cyan(f"  {display_name}")
                        write_at(term, 0, y + line_num, item_line)
                        line_num += 1

                        # Show description on next line if there's space
                        if line_num < height - footer_lines:
                            desc_line = term.black_on_cyan(f"     {description}")
                            write_at(term, 0, y + line_num, desc_line)
                            line_num += 1
                    else:
                        # Normal device
                        item_line = term.bold(f"  {display_name}")
                        write_at(term, 0, y + line_num, item_line)
                        line_num += 1

                        # Show description on next line if there's space
                        if line_num < height - footer_lines:
                            desc_line = term.white(f"     {description}")
                            write_at(term, 0, y + line_num, desc_line)
                            line_num += 1
                elif state.palette_mode == "rankings":
                    # Rankings items: (rank, artist_title, icon, rating_info, track_id)
                    rank, artist_title, icon, rating_info, track_id = item

                    # Truncate artist_title if too long
                    max_width = term.width - 20  # Leave room for rank, icon, and rating
                    if len(artist_title) > max_width:
                        artist_title = artist_title[: max_width - 3] + "..."

                    if is_selected:
                        # Selected item: highlighted background
                        item_line = term.black_on_cyan(f"  {rank} {icon} {artist_title}")
                        write_at(term, 0, y + line_num, item_line)
                        line_num += 1

                        # Show rating info on next line if there's space
                        if line_num < height - footer_lines:
                            rating_line = term.black_on_cyan(f"       {rating_info}")
                            write_at(term, 0, y + line_num, rating_line)
                            line_num += 1
                    else:
                        # Normal item
                        item_line = (
                            term.bold_yellow(f"  {rank}")
                            + term.white(f" {icon} ")
                            + term.cyan(artist_title)
                        )
                        write_at(term, 0, y + line_num, item_line)
                        line_num += 1
                else:
                    # Command/playlist items: (cat, cmd, icon, desc)
                    cat, cmd, icon, desc = item
                    cmd_text = f"{cmd:<20}"

                    if is_selected:
                        # Selected item: highlighted background
                        item_line = (
                            term.black_on_cyan(f"  {icon} ")
                            + term.black_on_cyan(cmd_text)
                            + term.black_on_cyan(f" {desc}")
                        )
                    else:
                        # Normal item
                        item_line = (
                            term.bold(f"  {icon} ")
                            + term.cyan(cmd_text)
                            + term.white(f" {desc}")
                        )

                    write_at(term, 0, y + line_num, item_line)
                    line_num += 1

                items_rendered += 1

    # Clear remaining lines
    while line_num < height - footer_lines:
        write_at(term, 0, y + line_num, "")
        line_num += 1

    # Footer help text - confirmation or normal mode
    if line_num < height:
        if state.confirmation_active:
            if state.confirmation_type == "delete_playlist":
                # Show playlist deletion confirmation
                playlist_name = state.confirmation_data.get("playlist_name", "Unknown")
                footer = f"   Delete '{playlist_name}'? [Enter/Y]es / [N]o"
                write_at(term, 0, y + line_num, term.yellow(footer))
            elif state.confirmation_type == "remove_track_from_playlist":
                # Show track removal confirmation
                track_title = state.confirmation_data.get("track_title", "Unknown")
                track_artist = state.confirmation_data.get("track_artist", "Unknown")
                footer = (
                    f"   Remove '{track_artist} - {track_title}'? [Enter/Y]es / [N]o"
                )
                write_at(term, 0, y + line_num, term.yellow(footer))
        else:
            # Normal footer with scroll indicator and help text
            if state.palette_mode == "search":
                # Track search footer - different help text based on mode
                if state.search_mode == "search":
                    total_items = len(state.search_filtered_tracks)
                    if total_items > content_height:
                        current_position = min(state.search_selected + 1, total_items)
                        footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter details  Esc cancel"
                    else:
                        footer = "   ↑↓ navigate  Enter details  Esc cancel"
                elif state.search_mode == "detail":
                    footer = "   ↑↓ navigate  Enter select  p/a/e shortcuts  Esc back"
            elif state.palette_mode == "playlist":
                # Playlist mode footer with view and delete key help
                total_items = len(filtered_commands)
                if total_items > content_height:
                    current_position = min(selected_index + 1, total_items)
                    footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter activate  v view  Del delete  Esc cancel"
                else:
                    footer = (
                        "   ↑↓ navigate  Enter activate  v view  Del delete  Esc cancel"
                    )
            elif state.palette_mode == "rankings":
                # Rankings mode footer with play key help
                total_items = len(filtered_commands)
                if total_items > content_height:
                    current_position = min(selected_index + 1, total_items)
                    footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter/p play  Esc cancel"
                else:
                    footer = "   ↑↓ navigate  Enter/p play  Esc cancel"
            else:
                # Command mode footer
                total_items = len(filtered_commands)
                if total_items > content_height:
                    current_position = min(selected_index + 1, total_items)
                    footer = f"   [{current_position}/{total_items}] ↑↓ navigate  Enter select  Esc cancel"
                else:
                    footer = "   ↑↓ navigate  Enter select  Esc cancel"

            write_at(term, 0, y + line_num, term.white(footer))
        line_num += 1


def _render_track_detail(
    term, state, track, y, line_num, height, footer_lines, content_height
):
    """
    Render combined detail view: metadata + actions.

    Shows track metadata at top, then actions menu at bottom with one action highlighted.

    Args:
        term: Terminal instance
        state: UI state
        track: Track dictionary
        y: Starting Y position
        line_num: Current line number
        height: Total palette height
        footer_lines: Number of footer lines
        content_height: Available content height

    Returns:
        Updated line_num
    """
    # Track metadata fields to display
    fields = [
        ("Title", track.get("title", "Unknown")),
        ("Artist", track.get("artist", "Unknown")),
        ("Album", track.get("album", "")),
        ("Genre", track.get("genre", "")),
        ("Year", str(track.get("year", "")) if track.get("year") else ""),
        ("BPM", str(track.get("bpm", "")) if track.get("bpm") else ""),
        ("Key", track.get("key_signature", "")),
    ]

    # Add tags and notes if present (database returns comma-separated strings from GROUP_CONCAT)
    tags = track.get("tags", "")  # String, not list
    if tags:
        fields.append(("Tags", tags))

    notes = track.get("notes", "")  # String, not list
    if notes:
        fields.append(("Notes", notes))

    # Render metadata fields
    for label, value in fields:
        if not value:  # Skip empty fields
            continue

        if line_num >= height - footer_lines:
            break

        detail_line = f"  {term.bold_cyan(label + ':')} {term.white(value)}"
        write_at(term, 0, y + line_num, detail_line)
        line_num += 1

    # Separator line before actions
    if line_num < height - footer_lines:
        write_at(term, 0, y + line_num, "")
        line_num += 1

    # Actions header
    if line_num < height - footer_lines:
        write_at(term, 0, y + line_num, "  " + term.bold_white("Actions:"))
        line_num += 1

    # Actions menu (4 items, one highlighted)
    actions = [
        ("Play", "p", "Play this track now"),
        ("Add to Playlist", "a", "Add to a playlist"),
        ("Edit Metadata", "e", "Edit track metadata"),
        ("Cancel", "Esc", "Go back"),
    ]

    for action_idx, (label, shortcut, desc) in enumerate(actions):
        if line_num >= height - footer_lines:
            break

        is_selected = state.search_detail_selection == action_idx
        action_text = f"  [{shortcut}] {label}"

        if is_selected:
            # Highlighted selection
            item_line = term.black_on_cyan(f"{action_text:<30}") + term.black_on_cyan(
                f" {desc}"
            )
        else:
            # Normal item
            item_line = term.bold_cyan(action_text) + term.white(f" - {desc}")

        write_at(term, 0, y + line_num, item_line)
        line_num += 1

    return line_num
