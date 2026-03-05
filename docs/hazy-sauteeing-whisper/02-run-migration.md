---
task: 02-run-migration
status: done
depends: [01-create-migration-script]
files:
  - path: ~/.local/share/music-minion/music_minion.db
    action: modify
---

# Run the Migration

## Context

Execute the migration script to split the 72 tracks, creating local versions and moving all relationships.

## Files to Modify/Create

- `~/.local/share/music-minion/music_minion.db` (modify - track records and FK tables)

**Note:** Waveform cache files are NOT copied - they regenerate on demand during first playback.

## Prerequisites

- **Stop all music-minion processes** before running (web backend, CLI). The `player_queue_state` table stores track IDs as TEXT and is not migrated - queue state may need re-queuing after migration.
- **Stop piserver Docker** before migration - databases are synced via Syncthing (`sendreceive` mode)

## Implementation Details

1. **Stop piserver Docker**
2. **Stop local processes**
3. **Backup database**
4. **Run migration script locally**
5. **Wait for Syncthing to propagate to piserver**
6. **Verify results**
7. **Restart piserver Docker**

## Verification

```bash
# 1. Stop piserver Docker
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose down'

# 2. Stop local processes (if running)
# Exit music-minion CLI / stop web backend

# 3. Pre-migration backup
cp ~/.local/share/music-minion/music_minion.db ~/.local/share/music-minion/music_minion.db.bak

# 4. Run migration locally
uv run python scripts/fix_soundcloud_local_path.py

# 5. Verify database state
sqlite3 ~/.local/share/music-minion/music_minion.db "
  SELECT COUNT(*) FROM tracks WHERE source='soundcloud' AND local_path IS NOT NULL;
  -- Should be 0

  SELECT COUNT(*) FROM tracks WHERE source='local' AND soundcloud_id IS NOT NULL;
  -- Should be 72 MORE than pre-migration baseline

  PRAGMA foreign_key_check;
  -- Should be empty
"

# 6. Wait for Syncthing to propagate (~30-60s for 27MB database)
# Verify both databases match:
watch -n5 "echo 'Local:' && md5sum ~/.local/share/music-minion/music_minion.db && echo 'Pi:' && ssh piserver 'md5sum ~/.local/share/music-minion/music_minion.db'"
# Wait until hashes match, then Ctrl+C

# 7. Restart piserver Docker
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose up -d'

# Functional tests (after restart)
# 1. Play "Overthinker (SHIX Flip)" - verify audio works
# 2. Check waveform loads
# 3. Verify playlist membership preserved
# 4. Check ratings intact
```
