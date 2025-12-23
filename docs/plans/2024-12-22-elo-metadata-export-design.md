# ELO Metadata Export Design

## Overview

Write ELO ratings to audio file metadata for visibility in MusicBee and Serato DJ.

## Metadata Fields

### TXXX Custom Fields (ID3/Vorbis/MP4)

| Field | Format | Description |
|-------|--------|-------------|
| `TXXX:GLOBAL_ELO` | `"1532"` | Track's global ELO rating |
| `TXXX:PLAYLIST_ELO` | `"1612"` | Track's playlist-specific ELO rating |

**Format by file type:**
- MP3 (ID3): `TXXX:GLOBAL_ELO`, `TXXX:PLAYLIST_ELO`
- Opus/OGG (Vorbis): `GLOBAL_ELO`, `PLAYLIST_ELO`
- M4A (MP4): `----:com.apple.iTunes:GLOBAL_ELO`, `----:com.apple.iTunes:PLAYLIST_ELO`

### COMMENT Field

Prepend playlist ELO with zero-padding for sortability:

```
1612 - Original comment text here
0987 - Another track comment
```

- 4-digit zero-padded (ELO typically 1000-2000)
- Enables "sort by comment" in DJ software for ELO-based ordering
- Only playlist ELO goes in comment (most relevant for DJ sets)

## Trigger Points

| Operation | GLOBAL_ELO | PLAYLIST_ELO | COMMENT |
|-----------|------------|--------------|---------|
| **Sync Full** (metadata section) | ✅ Write | ❌ Skip | ❌ Skip |
| **Playlist Export** (`--sync-metadata`) | ❌ Skip | ✅ Write | ✅ Prepend |

### Sync Full Behavior

During `sync full` command (metadata sync section):
1. Read track's global ELO from database
2. Write `TXXX:GLOBAL_ELO` to file
3. Do NOT modify COMMENT or PLAYLIST_ELO

### Playlist Export Behavior

During `export playlist <name> --sync-metadata`:
1. For each track in playlist:
   - Read track's playlist ELO for this specific playlist
   - Write `TXXX:PLAYLIST_ELO` to file (overwrites previous)
   - Read existing COMMENT, strip any existing ELO prefix
   - Prepend zero-padded playlist ELO: `{elo:04d} - {comment}`

**Note:** PLAYLIST_ELO represents the most recently exported playlist's rating. Exporting a different playlist overwrites the previous value.

## Implementation

### New Functions

**`domain/library/metadata.py`:**

```python
def write_elo_to_file(
    local_path: str,
    global_elo: float | None = None,
    playlist_elo: float | None = None,
    update_comment: bool = False,
) -> bool:
    """Write ELO ratings to audio file metadata.

    Args:
        local_path: Path to audio file
        global_elo: Global ELO rating to write to TXXX:GLOBAL_ELO
        playlist_elo: Playlist ELO to write to TXXX:PLAYLIST_ELO
        update_comment: If True and playlist_elo provided, prepend to COMMENT

    Returns:
        True if successful
    """

def strip_elo_from_comment(comment: str) -> str:
    """Remove ELO prefix from comment if present.

    '1532 - Original comment' -> 'Original comment'
    '1532' -> ''
    'No prefix here' -> 'No prefix here'
    """

def format_comment_with_elo(elo: float, existing_comment: str | None) -> str:
    """Format comment with zero-padded ELO prefix.

    format_comment_with_elo(1532, 'Great track') -> '1532 - Great track'
    format_comment_with_elo(987, None) -> '0987'
    """
```

### Modified Functions

**`domain/playlists/exporters.py`:**

```python
def export_playlist(
    ...
    sync_metadata: bool = False,  # NEW PARAMETER
) -> tuple[Path, int]:
    """Export playlist with optional metadata sync."""
```

**`domain/sync/engine.py`:**

Add global ELO writing to metadata sync section of `sync_full()`.

## DJ Workflow

1. Rate tracks via comparison mode (updates database)
2. Run `sync full` → GLOBAL_ELO written to all files
3. Export playlist with `--sync-metadata` → PLAYLIST_ELO + COMMENT updated
4. In Serato/MusicBee: sort by COMMENT column
5. Tracks appear in playlist ELO order (highest rated first)

## Edge Cases

- **No ELO rating:** Skip writing (don't write "1500" for unrated tracks)
- **Track in multiple playlists:** PLAYLIST_ELO reflects most recent export
- **Existing COMMENT with ELO prefix:** Strip old prefix before adding new
- **ELO > 9999 or < 0:** Clamp to 0000-9999 range (unlikely edge case)
