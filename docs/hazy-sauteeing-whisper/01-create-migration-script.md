---
task: 01-create-migration-script
status: done
depends: []
files:
  - path: scripts/fix_soundcloud_local_path.py
    action: create
---

# Create Migration Script for SoundCloud/Local Track Split

## Context

72 tracks have `source='soundcloud'` but also have `local_path` set due to a previous merge. This script will create separate local records and move relationships to them, keeping both soundcloud and local versions.

**Note:** All 72 tracks require new local records (no existing local duplicates found). Waveform cache files are NOT copied - they regenerate on demand during first playback (~1-2s latency).

## Files to Modify/Create

- `scripts/fix_soundcloud_local_path.py` (create)

## Implementation Details

Create a migration script:

### For each of the 72 tracks:
- INSERT new track with `source='local'`, copy all fields including `soundcloud_id`
- UPDATE all FK tables to point to new track ID
- UPDATE original soundcloud track: `SET local_path = NULL`

### FK Tables to Update

**Note:** `playlist_comparison_history` stores track IDs as TEXT - these are updated to maintain query consistency (comparisons represent the same underlying song, now referenced by local track ID).

**Intentionally NOT updated:** `active_playlist.last_played_track_id` and `radio_state.last_track_id` - these are ephemeral state that self-corrects on next playback.

**Tables:**
- `playlist_tracks` (UNIQUE on playlist_id, track_id)
- `ratings`, `notes`, `playback_sessions`, `tags`, `track_emojis`
- `track_dimension_votes`, `bucket_tracks`, `track_genres` (composite PKs)
- `radio_history`, `radio_skipped`, `track_listen_sessions`
- `playlist_elo_ratings`, `playlist_comparison_history` (TEXT columns!)
- `ai_requests`, `playlist_builder_skipped`, `playlist_builder_sessions`

### Script Features
- `--dry-run` flag to preview changes without committing
- Atomic transaction (rollback on failure)
- Pre/post verification queries

## Verification

```bash
# Dry run first
uv run python scripts/fix_soundcloud_local_path.py --dry-run

# Check output shows:
# - Number of tracks to migrate per scenario
# - FK tables that will be updated
# - No errors
```
