"""Track search utilities - filtering and search functions."""

from typing import Any


def filter_tracks(query: str, all_tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter tracks by query across all text fields.

    Searches: title, artist, album, genre, tags, notes
    Case-insensitive substring matching.

    Args:
        query: Search query string
        all_tracks: Full list of tracks to filter

    Returns:
        Filtered list of matching tracks (or all tracks if query is empty)

    Performance:
        ~3-5ms for 5000 tracks (pure Python)
    """
    if not query:
        return all_tracks  # Return all tracks if no query

    query_lower = query.lower()
    matches = []

    for track in all_tracks:
        # Concatenate searchable fields
        searchable = " ".join(
            [
                track.get("title", "") or "",
                track.get("artist", "") or "",
                track.get("album", "") or "",
                track.get("genre", "") or "",
                track.get("tags", "") or "",
                track.get("notes", "") or "",
            ]
        ).lower()

        if query_lower in searchable:
            matches.append(track)

    return matches
