---
task: 06-write-metadata-to-file
status: done
depends: [05-preview-and-confirm]
files:
  - path: scripts/enrich_metadata.py
    action: modify
---

# Write Metadata to File

## Context
After user confirmation, write the parsed metadata to the audio file using Mutagen. Support MP3 (ID3), Opus/FLAC (Vorbis), and M4A (MP4) formats.

## Files to Modify/Create
- scripts/enrich_metadata.py (modify)

## Implementation Details

### Use Existing Function
Reuse `write_metadata_to_file()` from `domain/library/metadata.py` - it already handles:
- Atomic writes (copy → modify temp → replace)
- MP3 (ID3), M4A (MP4), Opus, OGG, FLAC formats
- All the fields we need (title, artist, genre, year)

Note: Label field is skipped (not supported by existing function, rarely used in DJ software).

```python
from music_minion.domain.library.metadata import write_metadata_to_file

def apply_enrichment(local_path: str, parsed: dict) -> bool:
    """Write AI-parsed metadata to file."""
    return write_metadata_to_file(
        local_path=local_path,
        title=parsed["title"],
        artist=format_artist_string(parsed),
        genre=parsed.get("genre"),
        year=parsed.get("year"),
    )
```

### Prepare Metadata (for preview display)
```python
def prepare_metadata(parsed: dict) -> dict:
    """Convert AI output to display-ready metadata dict."""
    return {
        "title": parsed["title"],
        "artist": format_artist_string(parsed),
        "genre": parsed.get("genre"),
        "year": parsed.get("year"),
    }
```

## Verification
```bash
# Test on MP3
uv run python scripts/enrich_metadata.py /path/to/track.mp3
# Confirm with 'y', then verify:
uv run python scripts/read_metadata.py /path/to/track.mp3

# Test on Opus
uv run python scripts/enrich_metadata.py /path/to/track.opus
# Confirm with 'y', then verify

# Test on FLAC
uv run python scripts/enrich_metadata.py /path/to/track.flac
# Confirm with 'y', then verify
```

Expected: Metadata written correctly for all three formats.
