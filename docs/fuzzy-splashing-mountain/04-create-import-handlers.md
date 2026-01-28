# Create Import Handler Functions

## Files to Create
- `src/music_minion/domain/library/providers/youtube/import_handlers.py` (new)

## Implementation Details

Create orchestration functions that coordinate YouTube imports using the download module and database helpers.

### Data Classes

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ImportResult:
    """Result of an import operation - returned instead of logging directly."""
    tracks: list[Track]
    imported_count: int
    skipped_count: int
    failed_count: int
    failures: list[tuple[str, str]]  # (video_id, error_message)
```

### Required Functions

#### `import_single_video(url: str, artist: Optional[str], title: Optional[str], album: Optional[str]) -> Track`

Import a single YouTube video with optional user-controlled metadata.

**Steps**:
1. Extract youtube_id from URL using `download.extract_video_id()`
2. Check for duplicate using `database.get_track_by_youtube_id()`
   - If exists, raise `DuplicateVideoError(existing.id)`
3. **Download to temp directory first**: `output_dir / ".tmp" / "{youtube_id}.mp4"`
4. Extract metadata from download result (duration, title, uploader)
5. **Fall back to YouTube metadata if user didn't provide**:
   - title = user_title or video_metadata["title"]
   - artist = user_artist or video_metadata["uploader"]
   - album = user_album or ""
6. Insert track using `database.insert_youtube_track()`
7. **On successful insert, move file atomically**: `os.replace(temp_path, final_path)`
8. **On insert failure, delete temp file and re-raise**
9. Return Track object

**Atomic file handling**:
```python
temp_dir = output_dir / ".tmp"
temp_dir.mkdir(exist_ok=True)
temp_path = temp_dir / f"{youtube_id}.mp4"

try:
    # Download to temp
    temp_path, metadata = download.download_video(url, temp_dir)

    # Insert to database
    track_id = database.insert_youtube_track(...)

    # Move to final location atomically
    final_path = output_dir / sanitize_filename(title)
    os.replace(temp_path, final_path)

    # Update track with final path
    database.update_track_path(track_id, str(final_path))

except Exception:
    if temp_path.exists():
        temp_path.unlink()
    raise
```

**Error handling**:
- Duplicate detection before download (saves bandwidth)
- Download failures propagate with custom exceptions
- Database insertion failures trigger temp file cleanup

#### `import_playlist(playlist_id: str) -> ImportResult`

Bulk import all videos from a YouTube playlist with pre-download duplicate filtering.

**Steps**:
1. Get playlist info using `download.get_playlist_info()`
   - Extract playlist title (will be album name)
   - Extract all video IDs from playlist
2. **Batch check duplicates BEFORE downloading**:
   ```python
   video_ids = [v["id"] for v in playlist_info["videos"]]
   existing_ids = database.get_existing_youtube_ids(video_ids)
   new_video_ids = set(video_ids) - existing_ids
   ```
3. Check disk space: `download.check_available_space(output_dir, len(new_video_ids))`
4. Download only new videos: `download.download_playlist_videos(playlist_id, temp_dir, skip_ids=existing_ids)`
5. For each successful download:
   - Move to final location atomically
   - Collect track data for batch insert
6. **Batch insert using RETURNING clause**: `database.batch_insert_youtube_tracks(tracks_data)`
7. Update all tracks with final paths
8. **Return ImportResult** (don't log directly - let callers handle output)

**ImportResult construction**:
```python
successes, failures = download.download_playlist_videos(...)

return ImportResult(
    tracks=inserted_tracks,
    imported_count=len(inserted_tracks),
    skipped_count=len(existing_ids),
    failed_count=len(failures),
    failures=[(vid, str(exc)) for vid, exc in failures]
)
```

### Output Directory

Both functions should use:
```python
output_dir = Path.home() / "music" / "youtube"
output_dir.mkdir(parents=True, exist_ok=True)

# Temp directory for atomic operations
temp_dir = output_dir / ".tmp"
temp_dir.mkdir(exist_ok=True)
```

**Startup cleanup**: On provider init, delete any files in `.tmp/` (orphaned from previous failed imports).

### Imports Required

```python
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from loguru import logger

from music_minion.core import database
from music_minion.domain.library.models import Track
from .download import download_video, extract_video_id, get_playlist_info, download_playlist_videos, check_available_space, sanitize_filename
from .exceptions import DuplicateVideoError, InsufficientSpaceError
```

## Acceptance Criteria

- [ ] `ImportResult` dataclass defined with all statistics fields
- [ ] `import_single_video()` successfully imports with optional user metadata
- [ ] Falls back to YouTube metadata (title, uploader) when user doesn't provide
- [ ] Duplicate detection before download (saves bandwidth)
- [ ] Atomic file handling: temp → DB → move
- [ ] Failed DB insert triggers temp file cleanup
- [ ] `import_playlist()` batch checks duplicates BEFORE downloading
- [ ] Only downloads videos not already in database
- [ ] Uses batch insert with RETURNING clause
- [ ] Returns `ImportResult` instead of logging (callers handle output)
- [ ] Playlist title becomes album name for all tracks
- [ ] Temp directory cleaned up on startup

## Dependencies

- Task 02 (download module) must be complete
- Task 03 (database helpers) must be complete
