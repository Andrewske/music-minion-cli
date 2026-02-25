# Bidirectional Metadata Sync Redesign

## Overview

Redesign the local file sync system to support true bidirectional metadata sync between audio files and database. Replaces unreliable mtime-based change detection with content hashing. Adds clear `pull`/`push` semantics for explicit direction control.

**Scope:** LOCAL files only. Provider sync (SoundCloud, Spotify, YouTube) remains unchanged.

## Problem Being Solved

1. External editors (Serato, rekordbox) modify metadata without updating mtime
2. Current `sync` only imports COMMENT tags, not structured metadata (key, bpm)
3. No way to detect when both file and DB changed (conflicts)
4. Help text documents commands that don't exist

## Task Sequence

1. [01-database-migration.md](./01-database-migration.md) - Add `file_metadata_hash` column for content-based change detection
2. [02-sync-engine-core.md](./02-sync-engine-core.md) - Core sync functions: hash computation, action determination, sync execution
3. [03-command-handlers.md](./03-command-handlers.md) - New handlers for `sync`, `sync pull`, `sync push`, `sync status`
4. [04-router-and-help.md](./04-router-and-help.md) - Route new commands, update help text, deprecate `sync full`

## New Commands

| Command | Behavior |
|---------|----------|
| `sync` | Full sync: find new files + bidirectional merge |
| `sync --dry-run` | Preview what would change (no modifications) |
| `sync --ours` | Resolve conflicts: database wins |
| `sync --theirs` | Resolve conflicts: file wins |
| `sync pull` | Import changed files → database |
| `sync pull --all` | Full filesystem scan + import all |
| `sync push` | Export changed metadata → files |
| `sync push --all` | Export all metadata → files |

All commands support `--dry-run` flag for preview mode.

**Removed:** `sync full`, `sync status`, `library scan` (functionality consolidated into `sync`)

## Success Criteria

End-to-end verification:

1. **Import test:** Edit BPM in external DJ software → run `sync --dry-run` → shows "import" → run `sync` → DB updated
2. **Export test:** Edit BPM in Music Minion UI → run `sync --dry-run` → shows "export" → run `sync` → file updated
3. **Conflict test:** Edit same track in both places → `sync --dry-run` shows "conflict" with field diff → `sync --theirs` resolves
4. **Provider test:** Switch to SoundCloud library → `sync` works as API sync (unchanged)
5. **Force test:** `sync pull --all` re-imports all files regardless of hash
6. **Lock test:** Run two syncs simultaneously → second fails with "already running"

## Dependencies

- Existing: `mutagen` for metadata I/O
- Existing: `hashlib` (stdlib) for content hashing
- No new external dependencies required
