#!/usr/bin/env python3
"""
Bulk tag tracks with emoji.

Usage:
    # Tag all tracks in a playlist
    uv run scripts/bulk-tag-emoji.py --playlist "Workout Mix" --emoji "🔥"

    # Tag tracks by path pattern
    uv run scripts/bulk-tag-emoji.py --path-pattern "*/EDM/*" --emoji "⚡"

    # Tag specific track IDs
    uv run scripts/bulk-tag-emoji.py --track-ids 1,2,3,4 --emoji "💎"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import emoji as emoji_lib  # Renamed to avoid conflict with args.emoji
from music_minion.core.database import get_db_connection, normalize_emoji_id


def main() -> None:
    parser = argparse.ArgumentParser(description='Bulk tag tracks with emoji')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--playlist', help='Playlist name')
    group.add_argument('--path-pattern', help='File path pattern (e.g., "*/EDM/*")')
    group.add_argument('--track-ids', help='Comma-separated track IDs')
    parser.add_argument('--emoji', required=True, help='Emoji to add (Unicode or custom UUID)')
    args = parser.parse_args()

    emoji_id = normalize_emoji_id(args.emoji)

    with get_db_connection() as conn:
        # Get track IDs based on selection method
        if args.playlist:
            cursor = conn.execute(
                """
                SELECT t.id FROM tracks t
                JOIN playlist_tracks pt ON t.id = pt.track_id
                JOIN playlists p ON pt.playlist_id = p.id
                WHERE p.name = ?
                """,
                (args.playlist,)
            )
        elif args.path_pattern:
            cursor = conn.execute(
                "SELECT id FROM tracks WHERE local_path GLOB ?",
                (args.path_pattern,)
            )
        else:  # track_ids
            track_id_list = [int(x.strip()) for x in args.track_ids.split(',')]
            placeholders = ','.join('?' * len(track_id_list))
            cursor = conn.execute(
                f"SELECT id FROM tracks WHERE id IN ({placeholders})",
                track_id_list
            )

        track_ids = [row['id'] for row in cursor.fetchall()]

        if not track_ids:
            print("No tracks found matching criteria")
            sys.exit(0)

        print(f"Found {len(track_ids)} tracks. Adding emoji '{args.emoji}'...")

        # Use IMMEDIATE transaction for atomicity
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Auto-create emoji metadata if missing (same behavior as web UI)
            cursor = conn.execute(
                "SELECT type FROM emoji_metadata WHERE emoji_id = ?",
                (emoji_id,)
            )
            row = cursor.fetchone()
            if not row:
                # Check if it looks like a custom emoji UUID
                if len(emoji_id) == 36 and emoji_id.count('-') == 4:
                    print(f"Error: Custom emoji '{emoji_id}' not found in database")
                    print("Add custom emojis first with add-custom-emoji.py")
                    sys.exit(1)

                # Auto-create for Unicode emojis
                try:
                    name = emoji_lib.demojize(emoji_id).strip(':').replace('_', ' ')
                except Exception:
                    name = emoji_id

                conn.execute(
                    "INSERT INTO emoji_metadata (emoji_id, type, default_name, use_count) VALUES (?, 'unicode', ?, 0)",
                    (emoji_id, name)
                )
                print(f"Auto-created metadata for emoji '{emoji_id}' ({name})")

            # Bulk insert (INSERT OR IGNORE to skip duplicates)
            added = 0
            for track_id in track_ids:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO track_emojis (track_id, emoji_id) VALUES (?, ?)",
                    (track_id, emoji_id)
                )
                if cursor.rowcount > 0:
                    added += 1

            # Increment use_count once per actually added association
            if added > 0:
                conn.execute(
                    """
                    UPDATE emoji_metadata
                    SET use_count = use_count + ?, last_used = CURRENT_TIMESTAMP
                    WHERE emoji_id = ?
                    """,
                    (added, emoji_id)
                )

            conn.commit()
            print(f"✅ Added emoji to {added} tracks ({len(track_ids) - added} already had it)")

        except Exception as e:
            conn.rollback()
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
