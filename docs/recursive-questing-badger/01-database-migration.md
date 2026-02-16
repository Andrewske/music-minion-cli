---
task: 01-database-migration
status: done
depends: []
files:
  - path: src/music_minion/core/database.py
    action: modify
---

# Database Migration (v32)

## Context
Add the foundational `pin_order` column to support playlist pinning. This migration must run before any other pinning functionality can work.

## Files to Modify/Create
- src/music_minion/core/database.py (modify)

## Implementation Details

**Step 1: Update SCHEMA_VERSION**

Change line 20:
```python
SCHEMA_VERSION = 32
```

**Step 2: Add migration block after v31 migration**

```python
if current_version < 32:
    # Migration from v31 to v32: Playlist pinning
    print("  Migrating to v32: Adding playlist pinning support...")

    try:
        conn.execute("ALTER TABLE playlists ADD COLUMN pin_order INTEGER DEFAULT NULL")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise

    conn.execute("CREATE INDEX IF NOT EXISTS idx_playlists_pin_order ON playlists(pin_order)")

    print("  ✓ Migration to v32 complete: Playlist pinning support added")
    conn.commit()
```

**Step 3: Commit**

```bash
git add src/music_minion/core/database.py
git commit -m "feat: add pin_order column for playlist pinning (v32)"
```

## Verification

Run: `uv run music-minion --help` (triggers DB init)
Expected: See "Migrating to v32: Adding playlist pinning support..." message in output
