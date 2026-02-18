---
task: 06-migrate-existing-smart-playlists
status: done
depends:
  - 01-create-refresh-function
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Migrate Existing Smart Playlists

## Context
Existing smart playlists have no entries in `playlist_tracks`. We need a one-time migration to populate them.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

Add a migration in the database initialization to populate `playlist_tracks` for existing smart playlists.

**IMPORTANT:** Do NOT import from domain modules during migration - this can cause circular imports. Inline the SQL logic directly.

Find the migration section (after `if current_version < 33:`) and add:

```python
# Migration: Materialize existing smart playlists
if current_version < 34:
    print("  Migrating to v34: Materializing smart playlists...")

    # Get all smart playlists
    cursor = conn.execute("SELECT id, name FROM playlists WHERE type = 'smart'")
    smart_playlists = cursor.fetchall()

    for playlist in smart_playlists:
        playlist_id = playlist["id"]
        playlist_name = playlist["name"]

        try:
            # Get filters for this playlist
            cursor = conn.execute(
                "SELECT field, operator, value, conjunction FROM playlist_filters WHERE playlist_id = ? ORDER BY id",
                (playlist_id,)
            )
            filters = cursor.fetchall()

            if not filters:
                # No filters = no tracks
                print(f"    Skipping '{playlist_name}' (no filters)")
                continue

            # Build WHERE clause (simplified - handles common cases)
            # For complex filters, may need to run refresh after migration
            where_parts = []
            params = []
            for f in filters:
                field, operator, value = f["field"], f["operator"], f["value"]

                # Map field to column (key -> key_signature)
                column = "key_signature" if field == "key" else field

                # Skip emoji filters in migration (complex subquery)
                if field == "emoji":
                    continue

                if operator == "contains":
                    where_parts.append(f"{column} LIKE ?")
                    params.append(f"%{value}%")
                elif operator == "equals":
                    where_parts.append(f"{column} = ?")
                    params.append(value)
                elif operator == "gte":
                    where_parts.append(f"{column} >= ?")
                    params.append(value)
                elif operator == "lte":
                    where_parts.append(f"{column} <= ?")
                    params.append(value)
                # Add other operators as needed

            if not where_parts:
                print(f"    Skipping '{playlist_name}' (unsupported filters)")
                continue

            where_clause = " AND ".join(where_parts)

            # Clear existing playlist_tracks
            conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))

            # Insert matching tracks
            cursor = conn.execute(
                f"""
                SELECT id FROM tracks t
                WHERE {where_clause}
                AND t.id NOT IN (SELECT track_id FROM playlist_builder_skipped WHERE playlist_id = ?)
                ORDER BY artist, album, title
                """,
                tuple(params) + (playlist_id,)
            )
            track_ids = [row["id"] for row in cursor.fetchall()]

            # Batch insert
            conn.executemany(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position, added_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                [(playlist_id, tid, pos) for pos, tid in enumerate(track_ids)]
            )

            # Update track_count
            conn.execute(
                "UPDATE playlists SET track_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (len(track_ids), playlist_id)
            )

            print(f"    Materialized '{playlist_name}': {len(track_ids)} tracks")

        except Exception as e:
            print(f"    Warning: Failed to materialize '{playlist_name}': {e}")

    conn.execute("PRAGMA user_version = 34")
    conn.commit()
    print("  ✓ Migration to v34 complete: Smart playlists materialized")
```

**Note:** This migration handles common filter types (contains, equals, gte, lte). Complex playlists with emoji filters or OR conjunctions should have `refresh_smart_playlist_tracks()` called manually after migration, or will refresh automatically on next filter edit or sync.

## Verification
```bash
# Check current DB version
sqlite3 ~/.local/share/music-minion/music_minion.db "PRAGMA user_version"

# Run the app to trigger migration
uv run music-minion --web

# Verify smart playlists have tracks
sqlite3 ~/.local/share/music-minion/music_minion.db "
SELECT p.name, COUNT(pt.track_id) as track_count
FROM playlists p
LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
WHERE p.type = 'smart'
GROUP BY p.id
"
```
