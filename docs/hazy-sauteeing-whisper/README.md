# Fix SoundCloud Tracks with Local Paths

## Overview

72 tracks have `source='soundcloud'` but also have `local_path` set. This happened during a merge that consolidated tracks by `soundcloud_id` before the unique constraint was changed to `(soundcloud_id, library)`.

This plan creates separate local records for these tracks, moves all relationships (playlists, ratings, ELO, etc.) to the local versions, and updates the waveform endpoint to prioritize local files.

**Breakdown:**
- 72 tracks: Need new `source='local'` records created (no existing local duplicates found)

## Task Sequence

1. [01-create-migration-script.md](./01-create-migration-script.md) - Create Python script to split tracks and migrate FK relationships
2. [02-run-migration.md](./02-run-migration.md) - Execute migration with backup and verification
3. [03-update-waveform-endpoint.md](./03-update-waveform-endpoint.md) - Update waveform endpoint to prioritize local files (can run in parallel with 01-02)

## Success Criteria

1. `SELECT COUNT(*) FROM tracks WHERE source='soundcloud' AND local_path IS NOT NULL` returns **0**
2. `SELECT COUNT(*) FROM tracks WHERE source='local' AND soundcloud_id IS NOT NULL` returns **72 MORE** than pre-migration baseline
3. `PRAGMA foreign_key_check` returns **empty** (no FK violations)
4. Playing "Overthinker (SHIX Flip)" works with waveform displayed
5. Playlist memberships and ratings are preserved on local tracks

## Dependencies

- Database backup before migration
- Stop piserver Docker before migration (databases synced via Syncthing)
- Web backend running for verification tests
