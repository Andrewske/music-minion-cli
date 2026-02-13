# ELO Metadata Export

## Overview

Write ELO ratings to audio file metadata for visibility in MusicBee and Serato DJ. This enables sorting tracks by ELO rating in DJ software.

**Trigger Points:**
| Operation | TXXX:GLOBAL_ELO | TXXX:PLAYLIST_ELO | COMMENT |
|-----------|-----------------|-------------------|---------|
| `sync full` | Write | Skip | Skip |
| `export playlist --sync-metadata` | Skip | Write | `1532 - comment` |

**DJ Workflow:**
1. Rate tracks via comparison mode
2. Run `sync full` to write GLOBAL_ELO to files
3. Export playlist with `--sync-metadata` to write PLAYLIST_ELO + COMMENT
4. In Serato/MusicBee: sort by COMMENT column for ELO-based ordering

## Task Sequence

1. [01-core-elo-functions.md](./01-core-elo-functions.md) - Add ELO writing functions to metadata.py
2. [02-unit-tests.md](./02-unit-tests.md) - Create unit tests for core functions
3. [03-sync-full-integration.md](./03-sync-full-integration.md) - Integrate GLOBAL_ELO into sync full command
4. [04-playlist-export-integration.md](./04-playlist-export-integration.md) - Add --sync-metadata flag to playlist export

## Success Criteria

- [ ] `sync full` writes GLOBAL_ELO to all rated tracks
- [ ] `export playlist <name> --sync-metadata` writes PLAYLIST_ELO and updates COMMENT
- [ ] COMMENT field uses zero-padded ELO (e.g., `1532 - existing comment`) for proper sorting
- [ ] Unrated tracks (ELO=1500) are skipped
- [ ] All unit tests pass
- [ ] Works with MP3, M4A, Opus, and OGG formats

## Execution Instructions

1. Execute tasks in numerical order (01 → 04)
2. Each task file contains:
   - Files to modify/create
   - Implementation details
   - Acceptance criteria
   - Dependencies
3. Verify acceptance criteria before moving to next task

## Dependencies

- Mutagen library (already installed)
- Existing `write_metadata_to_file()` pattern in metadata.py for atomic writes
