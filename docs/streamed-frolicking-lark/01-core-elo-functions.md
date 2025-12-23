# Core ELO Writing Functions

## Files to Modify/Create
- `src/music_minion/domain/library/metadata.py` (modify)

## Implementation Details

Add all core ELO writing functions to the existing metadata module.

### 1.1 Add imports
```python
from mutagen.id3 import TXXX, COMM  # Add to existing ID3 imports
import re
```

### 1.2 Add `strip_elo_from_comment(comment: str | None) -> str`
- Regex `^\d{4}(?:\s*-\s*)?` to strip "NNNN - " prefix
- Handle None/empty gracefully
- Examples:
  - `'1532 - Original comment'` -> `'Original comment'`
  - `'1532'` -> `''`
  - `'No prefix here'` -> `'No prefix here'`
  - `None` -> `''`

### 1.3 Add `format_comment_with_elo(elo: float, existing_comment: str | None) -> str`
- Zero-pad to 4 digits: `f"{int(round(elo)):04d}"`
- Clamp to 0-9999 range
- Strip existing ELO prefix before prepending
- Examples:
  - `format_comment_with_elo(1532, 'Great track')` -> `'1532 - Great track'`
  - `format_comment_with_elo(987, None)` -> `'0987'`
  - `format_comment_with_elo(1532, '1400 - Old prefix')` -> `'1532 - Old prefix'`

### 1.4 Add format-specific helpers

**`_write_elo_id3(audio, global_elo, playlist_elo, update_comment)`**
- Write `TXXX:GLOBAL_ELO` and `TXXX:PLAYLIST_ELO` frames
- Update COMM frame if `update_comment=True`

**`_write_elo_mp4(audio, global_elo, playlist_elo, update_comment)`**
- Write `----:com.apple.iTunes:GLOBAL_ELO` and `----:com.apple.iTunes:PLAYLIST_ELO`
- Update `\xa9cmt` comment tag if `update_comment=True`

**`_write_elo_vorbis(audio, global_elo, playlist_elo, update_comment)`**
- Write `GLOBAL_ELO` and `PLAYLIST_ELO` Vorbis comments
- Update `COMMENT` tag if `update_comment=True`

### 1.5 Add main function
```python
def write_elo_to_file(
    local_path: str,
    global_elo: float | None = None,
    playlist_elo: float | None = None,
    update_comment: bool = False,
) -> bool:
```
- Skip if ELO is None or 1500 (unrated)
- Use atomic write pattern (same as existing `write_metadata_to_file`)
- Return True on success, False on failure

## Acceptance Criteria
- [ ] All 5 functions added to metadata.py
- [ ] Functions follow existing code patterns (atomic writes, Mutagen usage)
- [ ] Skip writing for unrated tracks (ELO = 1500)
- [ ] Zero-padding works correctly for ELO < 1000

## Dependencies
None - this is the foundational task.
